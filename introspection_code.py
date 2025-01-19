# -------------------------------------------------------------------------------------------
# Ecriture de code permettant de faire l'introspection des codes sources d'un projet Python 
# Y. Stroppa
# SPGoO 
# Janvier 2025 
# -------------------------------------------------------------------------------------------

# -------------------------------------------------------------------------------------------
# Modifications :
#
# -------------------------------------------------------------------------------------------
import pymongo
import re
import os
import string
import sys
import getopt
import json
import collections
import glob
from neo4j import GraphDatabase

# -----------------------------------------
# Connexion a la base de donnees
# -----------------------------------------
myclient = pymongo.MongoClient("mongodb://192.168.1.5:27017/",username="ystroppa",password="password",authSource="genielog",authMechanism='SCRAM-SHA-1')
mydb = myclient["genielog"]
mycol = mydb["bibliotheque"]


# -----------------------------------
# Connexion à neo4j 
# -----------------------------------
#uri = "neo4j:///localhost:7690"
uri = "bolt://192.168.1.5:7687"
auth = ("neo4j", "password")
user, pwd = auth
db = None

#driver= GraphDatabase.driver(uri, auth=auth)
#driver.verify_connectivity()
#print("Connection established.")

# Gn = Neo4jConnection(uri, user, pwd)
def load_IN_PDB_in_Gn(Gn,query):
    """ 
    Ecriture des entrees dans neo4j
    """
    return Gn.execute_query(query, database_="neo4j") 

# essai de requete neo4j 
#query="MERGE (aizynthfinderchem:Files {name:'aizynthfinder.chem'})"
#load_IN_PDB_in_Gn(driver,query)


#fichiers_exclus=["./introspection_code.py"]
fichiers_exclus=["./introspection_code.py"]

# -------------------------------------
# Declarations des variables globales
# -------------------------------------
log_file = open("spgoo_messages.log","w")
log_error_file = open("spgoo_messages_erreurs.log","w")

# -------------------------------------
# Fonctions utilitaires
# -------------------------------------

def write_log(*args):
    line = ' '.join([str(a) for a in args])
    log_file.write(line+'\n')


def write_error(*args):
    line = ' '.join([str(a) for a in args])
    log_error_file.write(line+'\n')


def analyse_arbre_dependance(_file,structure):
    """
        Construction de l'arbre des dépendances 
        Ecriture des relations entre _file et les éléments dans dependances pour les entrées 
        import, import_as et from 
    """
    dependances= structure["dependances"]
    # traitement des imports
    print("Ecriture des dependances import") # attention au filename sans l'extension 
    post_file=_file.replace("./","").replace(".py","")
    query=" MERGE (" +post_file+":Aizynthfinder {name:'"+_file+"'})"
    for entree in dependances["import"]:    
        query +="MERGE (" +entree+":Librairies {name:'"+entree+"'})"
        query +="MERGE ("+post_file+")-[:import]->("+entree+")"
        load_IN_PDB_in_Gn(driver,query)
    
    # traitement des imports_as mais on ajoute dans le relation les alias 
    print("Ecriture des dépendances import_as")
    for entree in dependances["import_as"]:  
        # 'import_as': [], 'from': [{'__future__': 'annotations'}....{'aizynthfinder.analysis': ['RouteCollection', 'RouteSelectionArguments', 'TreeAnalysis', '']}
        post_file=_file.replace("./","").replace(".py","")
        queyr="MERGE ("+post_file+":Aizynthfinder {name:'"+_file+"'})"
        for key in entree:      
            query+="MERGE ("+key+":Librairies {name:'"+key+"'})"
            query+="MERGE ("+post_file+")-[r:import_as]->("+key+")"
            load_IN_PDB_in_Gn(driver,query)

    # traitement des from
    print("Ecriture des dépendances from")
    for entree in dependances["from"]:
        post_file=_file.replace("./","").replace(".py","")
        query="MERGE ("+post_file+":Aizynthfinder {name:'"+_file+"'})"
        # attention la value peut-etre de type simple ou multiple 
        #print(entree)
        for clefs in entree:
            # on verifie que si la clefs commence par aizynthfider ça fait partie du projet 
            if "aizynthfinder" in clefs:
                query+="MERGE ("+clefs.replace("-","")+":Aizynthfinder {name:'"+clefs.replace("-",".")+"'})"
            else : 
                query+="MERGE ("+clefs.replace("-","")+":Librairies {name:'"+clefs.replace("-",".")+"'})"
            if isinstance(entree[clefs],list): 
                chaine=""
                for key in entree[clefs] :
                    chaine+="'"+key+"',"
                query+="MERGE ("+post_file.replace("-","")+")-[r:from {name:["+chaine[:-1]+"]}]->("+clefs.replace("-","")+")"
                load_IN_PDB_in_Gn(driver,query)
            else: 
                #print(entree[clefs])
                query+="MERGE ("+post_file.replace("-","")+")-[r:from {objet:'"+entree[clefs]+"'}]->("+clefs.replace("-","")+")"
                load_IN_PDB_in_Gn(driver,query)


def traite_ligne(ligne):
    """
        Fonction de traitement de la ligne 
    """
    #print(ligne)
    ligne=ligne.strip()
    S_name_fct=ligne[ligne.index("def")+4:ligne.index("(")]
    S_args=ligne[ligne.index("(")+1:ligne.rfind(")")]
    T_args=[i.strip() for i in S_args.split(",")]
    # annotation du type de retour 
    S_retour="";
    if "->" in ligne:
        S_retour=ligne[ligne.index("->")+2:ligne.rfind(":")].strip()
    return S_name_fct,T_args,S_retour

def fonction_traitement(_file):
   """
        Objet : fonction d'analyse et de reconstruction des infos pour un fichier python
        input: _file nom du fichier a explorer
   """
   print("------------------------------")
   print("Traitement du fichier" + _file)
   print("------------------------------")

   D_struct=dict()
   D_struct["description"]=_file
   D_struct["dependances"]={"import":[],"import_as":[],"from":[],"conditionnel":[]}
   D_struct["def"]=dict()
   D_struct["comments"]=""
   D_struct["classes"]=dict()

   file = open(_file, encoding="utf8")
   data=file.read()
   file.close()
   write_log("fichier en cours de traitement " + fichier)
   Data_lignes=data.splitlines()
   nb_lignes=len(Data_lignes)
   write_log("nb de lignes " + str(nb_lignes))
   tab=_file.split(".")
   output_fichier =tab[0]+"output.json"
   # --------------------------------------------------------------------
   # Analyse des lignes pour identifier les différentes déclarations
   # dependances 
   # classes 
   # fonctions 
   # pour reconstruire le fichier json resultant de cette analyse
   # --------------------------------------------------------------------
   encours=D_struct
   B_plusieursLignes=False
   B_comments=False
   S_tabulation=0
   B_from_multiligne=False
   B_classe_encours=False
   B_type_checking=False
   N_status_space_classe=0
   D_pointer_commentaires=""

   B_directives_dataclass=False
   B_directives_classmethod=False
   B_chgt_contexte=False
   TD_attributs={}
   for ligne in Data_lignes:
       # prise en compte de la tabulation a chaque ligne 
       N_tabulation= len(ligne) -len(ligne.lstrip())
       if B_classe_encours:
           N_status_space_classe=N_tabulation
           B_classe_encours=False

       if B_type_checking:
           N_status_checking=N_tabulation
           B_type_checking=False
       # -----------------------------------------------------------------------------------
       # interpretation des commentaires a placer au bon niveau  regarder les tabulations
       # deux situations : sur une ligne ou plusieurs lignes
       # -----------------------------------------------------------------------------------
       if '"""' in ligne.strip() and ligne.strip().endswith('"""') and len(ligne) >20 :
           B_comments=False
           S_comments=ligne.replace('"""',"").strip()
           if isinstance(D_pointer_commentaires,dict):
                D_pointer_commentaires["comments"]=S_comments
           S_comments=""
           continue

       if '"""' in ligne.strip() and not B_comments:
           B_comments=True
           S_comments=ligne.replace('"""',"").strip()
           continue

       if ligne.endswith('"""'):
           B_comments=False
           S_comments=S_comments.replace("\n"," ")
           if isinstance(D_pointer_commentaires,dict): 
                D_pointer_commentaires["comments"]=S_comments.strip()
           S_comments=""
           continue

       if B_comments:
           S_comments+=" "+ligne.strip()
           continue

       # ------------------------------------------------------------------------------------
       # Lecture des directives via le caractère @ # plusieurs directives a prendre en compte 
       # @dataclass @classmethod 
       # description des attributs juste en dessous du nom de la classe 
       # ------------------------------------------------------------------------------------
       if "@dataclass" in ligne:
           B_directives_dataclass=True
           print("directives")
           continue
       if "@classmethod" in ligne:
           B_directives_classmethod=True
           continue

       # -----------------------------------------------------------------------------------
       # Interpretation des directives d'import ou de from 
       # -----------------------------------------------------------------------------------
       if ligne.lstrip().startswith('from '):
       #if "from " in ligne:
           # attention le from peut etre sur plusieurs lignes
           if "(" in ligne:
               B_from_multiligne=True
               S_ligne_cumule=ligne
               continue
           else: 
               #print("traitement de from") # {"__future__":["annotations"]}
               ligne=ligne.lstrip()
               D_struct["dependances"]["from"].append({ligne[5:ligne.index("import")-1].replace(".","-"):ligne[ligne.index("import")+7:]})
               #D_struct["dependances"]["from"].append({ligne[5:ligne.index("import")-1]:ligne[ligne.index("import")+7:]})
           continue

       if B_from_multiligne:
           S_ligne_cumule+=ligne
           S_ligne_cumule=S_ligne_cumule.replace("\n"," ")
           if ")" in ligne:
               # on traite la totalite de la declaration
               #print("condi " + S_ligne_cumule)
               S_ligne_cumule=S_ligne_cumule.lstrip()
               print(S_ligne_cumule)
               S_key=S_ligne_cumule[5:S_ligne_cumule.index("import")-1].replace(".","-")  # attention à supprimer les . 
               S_values=S_ligne_cumule[S_ligne_cumule.index("import")+7:].replace("(","").replace(")","")
               T_values=[i.strip() for i in S_values.split(",")]
               D_struct["dependances"]["from"].append({S_key:T_values})
               S_ligne_cumule=""
               B_from_multiligne=False
           continue

       if ligne.startswith('import '):
           # deux cas avec ou sans as
           if "as " in ligne:
               forme=ligne[7:ligne.index("as")-1].replace(".","-")
               D_struct["dependances"]["import_as"].append({forme:ligne[ligne.index("as"):]})
           else:
               forme=ligne[7:].replace(".","-")
               D_struct["dependances"]["import"].append(forme)
           continue
       # on supprime tous les espaces 
       ligne_without_spaces=ligne.translate({ord(c): None for c in string.whitespace})
       if 'ifTYPE_CHECKING:' in ligne_without_spaces:
           # chargement conditionnel 
           B_type_checking=True

       # -----------------------------------------------------------------------------------
       # prise en compte des #  
       # -----------------------------------------------------------------------------------
       # il faut extraire les indications après un # éventuel dans la ligne
       if "#" in ligne:
           ligne=ligne[0:ligne.index("#")-1].strip()

       # -----------------------------------------------------------------------------------
       # Extraction lors de classe des attributs : methode self   
       # -----------------------------------------------------------------------------------
       #if "self." in ligne:
       if re.search('self\.[a-zA-Z._ ]*=', ligne)!= None:
           if "=" in ligne:
               if ligne.index("=")> ligne.index("self."):
                  S_attribut_complet=ligne[ligne.index("self.")+5:ligne.index("=")-1]
                  # on saute les elements si il y a plusieurs . 
                  if S_attribut_complet.count(".")>0:
                    continue
                  # il faut separer si c'est le cas le nom de l'attribut et le type annotation 
                  if ":" in S_attribut_complet:
                      S_name_attribut=S_attribut_complet.split(":")[0]
                      S_type_attribut=S_attribut_complet.split(":")[1]
                  else:
                      S_name_attribut=S_attribut_complet
                      S_type_attribut=""
                  TD_attributs[S_name_attribut]={"type":S_type_attribut}
           continue

       # -----------------------------------------------------------------------------------
       # Extraction des classes    
       # -----------------------------------------------------------------------------------
       if "class " in ligne:  #  detection de la classe si elle existe 
           # on verifie si heritage dans la declaration 
           #parent=re.findall(r"\([a-zA-Z]+[.]*[a-zA-Z]*\)",ligne)
           parent=re.findall(r"\([a-zA-Z., _]*\)",ligne)
           heritage=""
           if len(parent)>0 :
               # il y a heritage et il faut extraire la parent 
               heritage=parent[0].replace("(","").replace(")","")
               ligne=ligne[0:ligne.index("(")-1]+":"

           TD_attributs={}   # tableau des attributs de la classe plusieurs descriptions possibles 
           S_classe=re.split('\s+', ligne)[1][:-1]
           if heritage !="" :
               D_struct["classes"][S_classe]={"parent":heritage,"attributs":{},"def":{}}   # attention au polymorphisme
           else:
               D_struct["classes"][S_classe]={"attributs":{},"def":{}}   # attention au polymorphisme
           encours=D_struct["classes"][S_classe] 
           D_pointer_commentaires=encours
           # On memorise la tabulation de la classe pour els afefctations des fonctions 
           B_classe_encours=True
           B_chgt_contexte=False
           #N_status_space_classe=N_tabulation
           continue

       if N_tabulation<N_status_space_classe:
           # affectation de la fonction à la classe 
           encours["attributs"]=TD_attributs.copy()
           B_chgt_contexte=True
           B_directives_dataclass=False

       if len(ligne.strip())==0:
           continue

       if N_tabulation==0:
           encours=D_struct


       # ---------------------------------------------
       # Extraction des attributs si annotation
       # ---------------------------------------------
       if not B_classe_encours and B_directives_dataclass and not B_chgt_contexte:
           # chaque ligne est une declarationa on s'arrete au caractère = pour avoir le nom
           # de la variable et son type
           if "=" in ligne:
                S_attribut_complet=ligne[0:ligne.index("=")-1]
                #S_name_attribut=S_attribut_complet.strip().split(":")[0]
                # verifier si il y a : et qu'il soit avant le = 
                if ":" in S_attribut_complet:
                    S_name_attribut=S_attribut_complet.strip().split(":")[0]
                    S_type_attribut=S_attribut_complet.strip().split(":")[1]
                    TD_attributs[S_name_attribut]={"type":S_type_attribut}
                else:
                    S_name_attribut=S_attribut_complet.strip()
                    TD_attributs[S_name_attribut]={"type":""}


       # -----------------------------------------------------------------------------------
       # Extraction des fonctions    
       # -----------------------------------------------------------------------------------
       # définition de la fonction sur une seule ligne attention au polymorphisme 
       if "def " in ligne  and ligne.strip().endswith(":"):  
           #print(ligne)
           # def to_json(self, include_metadata=False) -> str:
           S_name_fct, T_args,S_retour =traite_ligne(ligne)
           if S_name_fct in encours["def"]:
                tempo=encours["def"][S_name_fct].copy()
                encours["def"][S_name_fct]=[]
                encours["def"][S_name_fct].append(tempo)
                encours["def"][S_name_fct].append({"args":T_args,"return":S_retour})
           else:
                encours["def"][S_name_fct]={"args":T_args,"return":S_retour}
           D_pointer_commentaires=encours["def"][S_name_fct]
           continue

       # définition de la fonction sur plusieurs lignes
       if "def " in ligne  and not ligne.endswith(":"):  
           S_ligne_cumule=""
           B_plusieursLignes=True
           S_ligne_cumule+=ligne
           #print("declaration sur plusieurs lignes" )
           continue 

       if B_plusieursLignes:
           if ligne.endswith(":"):
               S_ligne_cumule+=ligne
               S_ligne_cumule=S_ligne_cumule.replace("\n","")
               B_plusieursLignes=False
               # on peut traiter l'ensemble de la declaration
               S_name_fct, T_args,S_retour=traite_ligne(S_ligne_cumule)
               encours["def"][S_name_fct]={"args":T_args,"return":S_retour}
               D_pointer_commentaires=encours["def"][S_name_fct]
               S_ligne_cumule=""
           else: 
               S_ligne_cumule+=ligne


   print(D_struct)
   # insertion dans la base de données mongodb
   #mycol.insert_one(D_struct)
   #analyse_arbre_dependance(_file,D_struct)
# ----------------------------------------------------------------------------------------------
# partie principale de traitement : liste de tous les fichiers et appel du traitement de chacun 
# à la lecture des fichiers, on complète la structure globale : forme_cumul_unicite
# ----------------------------------------------------------------------------------------------
#path = r'*.py'
path = './**/*.py'
#glob.glob('./**/*.py', recursive=True)
dir_list=glob.glob(path, recursive=True)
for fichier in dir_list:
    if fichier not in fichiers_exclus:
        fonction_traitement(fichier)

#with open("global_output.json", "w", encoding='utf8') as outfile:
#   json.dump(forme_cumul_unicite,outfile,ensure_ascii=False,indent=4)

