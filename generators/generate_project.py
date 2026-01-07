import random
import requests
import sys, os
from datetime import datetime, timedelta  # ✅ correction ici
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from dolibarr_api import *
from utils import *

def generate_project(
    dateCreate,
    nbTasks,
    nbtasksTime,
    retDataUser,
    retDataThirdParties,
    nbContactsMax=5,
    testing=False
):

    urlProjects = urlBase + "projects/"
    urlTasks = urlBase + "tasks"

    # --- Dates ---
    dateCreateWithTime = dateCreate + timedelta(
        hours=random.randint(6, 19),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59)
    )

    dateStart = fake.date_time_between(start_date=dateCreate, end_date=dateCreate + timedelta(days=30))
    dateEnd = fake.date_time_between(start_date=dateStart, end_date=dateStart + timedelta(days=180))
    dateNow = datetime.now()  # ✅ fix

    diffDaysEndNow = (dateNow - dateEnd).days
    diffDaysStartNow = (dateNow - dateStart).days

    # --- Statut projet ---
    if diffDaysEndNow > 365:
        projectStatus = 2  # closed
    elif 183 <= diffDaysEndNow <= 365:
        projectStatus = random.choice([1,2])
    elif diffDaysEndNow < 183 and diffDaysStartNow <= 0:
        projectStatus = random.choice([0,1,2])
    elif diffDaysStartNow > 0:
        projectStatus = random.choice([0,1])
    else:
        projectStatus = 0

    dateClose = None
    if projectStatus == 2:  # closed
        choice = random.choice(["before","equal","after"])
        if choice == "before":
            dateClose = dateEnd - timedelta(days=random.randint(1,5))
        elif choice == "after":
            max_days = max((dateNow - dateEnd).days, 1)
            dateClose = dateEnd + timedelta(days=random.randint(1, min(5, max_days)))
        else:
            dateClose = dateEnd

    dataProject = {
        "date_start": dateStart.timestamp(),
        "date_end": dateEnd.timestamp(),
        "ref": "auto",
        "title": fake.catch_phrase(),
        "description": fake.text(max_nb_chars=200),
        "date_close": dateClose.timestamp() if dateClose else None,
        "usage_task": "1",
        "budget_amount": random.randint(500, 10000),
        "socid": get_random_client(retDataThirdParties),
        "usage_bill_time": "0",
        "status": projectStatus,
        "public": 1
    }

    # --- Création projet ---
    try:
        r = requests.post(urlProjects, headers=headers, json=dataProject)
        if r.status_code != 200:
            print("❌ Erreur création projet:", r.status_code, r.text)
            return None
        projectID = r.json()["id"] if isinstance(r.json(), dict) else int(r.text.strip())
        if testing: print(f"✅ Projet créé ID={projectID}, statut={projectStatus}")
    except Exception as e:
        print("❌ Exception création projet:", e)
        return None

    # --- Mise à jour post-création ---
    dataUpdate = {
        "date_c": dateCreateWithTime.strftime("%Y-%m-%d %H:%M:%S"),
        "note_private": fake.text(max_nb_chars=200),
        "note_public": fake.text(max_nb_chars=200)
    }
    try:
        rU = requests.put(urlProjects + str(projectID), headers=headers, json=dataUpdate)
        if rU.status_code != 200:
            print("❌ Erreur update projet:", rU.status_code, rU.text)
        elif testing:
            print("✅ Update projet terminé")
    except Exception as e:
        print("❌ Exception update projet:", e)

    # --- Contacts projet ---
    urlContactProject = urlBase + f"projects/{projectID}/contacts"
    projectContacts = []

    if nbContactsMax > 0:
        nbProjectContacts = random.randint(1, nbContactsMax)
        for _ in range(nbProjectContacts):
            source = random.choice(["internal","external"])
            typeContact = random.choice(["PROJECTCONTRIBUTOR","PROJECTLEADER"])
            randomId = get_random_user(retDataUser)['id'] if source=="internal" else get_random_client(retDataThirdParties)
            dataContact = {"fk_socpeople": randomId, "type_contact": typeContact, "source": source}
            try:
                rC = requests.post(urlContactProject, headers=headers, json=dataContact)
                if rC.status_code != 200:
                    print(f"❌ Erreur ajout contact {source}: {rC.status_code}, {rC.text}")
                else:
                    projectContacts.append(dataContact)
                    if testing: print(f"👤 Contact {source} ajouté:", dataContact)
            except Exception as e:
                print(f"❌ Exception ajout contact {source}:", e)

    # --- Création tâches ---
    if nbTasks > 0:
        nbTasksProject = random.randint(1, nbTasks)
        for i in range(nbTasksProject):
            if projectStatus == 2:
                taskStatus = 3  # closed
            elif projectStatus == 1:
                taskStatus = random.choice([0,1,2,3])
            else:
                taskStatus = 0

            dateTaskC = fake.date_time_between_dates(dateStart, dateEnd)
            dateTaskO = fake.date_time_between_dates(dateTaskC, dateEnd)
            dateTaskE = fake.date_time_between_dates(dateTaskO, dateEnd)

            dataTask = {
                "ref": "auto",
                "fk_project": projectID,
                "date_start": dateTaskO.timestamp(),
                "date_end": dateTaskE.timestamp(),
                "label": fake.catch_phrase(),
                "description": fake.text(max_nb_chars=200),
                "planned_workload": fake.random_int(min=1,max=20)*3600,
                "note_private": fake.text(max_nb_chars=200),
                "note_public": fake.text(max_nb_chars=200),
                "status": 1  # draft initial
            }

            try:
                rT = requests.post(urlTasks, headers=headers, json=dataTask)
                if rT.status_code != 200:
                    print(f"❌ Erreur création tâche {i+1}: {rT.status_code} {rT.text}")
                    continue
                taskID = rT.json()["id"] if isinstance(rT.json(), dict) else int(rT.text.strip())
                if testing: print(f"📝 Tâche créée ID={taskID}, statut draft")

                # --- Update status tâche ---
                dataUpdateTask = {"status": taskStatus, "date_c": dateTaskC.timestamp()}
                rU = requests.put(urlTasks + str(taskID), headers=headers, json=dataUpdateTask)
                if rU.status_code != 200:
                    print(f"❌ Erreur update tâche {taskID}: {rU.status_code} {rU.text}")
                elif testing:
                    print(f"✅ Update tâche {taskID}, statut={taskStatus}")

                # --- Contacts tâche ---
                if projectContacts:
                    nbTaskContacts = random.randint(1, len(projectContacts))
                    taskContacts = random.sample(projectContacts, nbTaskContacts)
                    for tc in taskContacts:
                        dataTaskContact = {
                            "fk_socpeople": tc["fk_socpeople"],
                            "type_contact": random.choice(["TASKEXECUTIVE","TASKCONTRIBUTOR"]),
                            "source": tc["source"]
                        }
                        try:
                            rC = requests.post(urlTasks + str(taskID)+"/contacts", headers=headers, json=dataTaskContact)
                            if rC.status_code != 200:
                                print(f"❌ Erreur ajout contact tâche {taskID}: {rC.status_code} {rC.text}")
                            elif testing:
                                print(f"✅ Contact tâche ajouté: {dataTaskContact}")
                        except Exception as e:
                            print(f"❌ Exception contact tâche {taskID}:", e)

                # --- Pointages ---
                if taskStatus > 0 and nbtasksTime > 0:
                    nbTimes = random.randint(1, nbtasksTime)
                    for t in range(nbTimes):
                        userId = random.choice(taskContacts)["fk_socpeople"] if taskContacts else 0
                        dataTime = {
                            "date": fake.date_time_between_dates(dateTaskO, dateTaskE).strftime("%Y-%m-%d %H:%M:%S"),
                            "duration": fake.random_int(min=300,max=3600),
                            "user_id": userId,
                            "note": fake.sentence(nb_words=10),
                            "progress": fake.random_int(min=0,max=100)
                        }
                        try:
                            rTime = requests.post(urlTasks + str(taskID)+"/addtimespent", headers=headers, json=dataTime)
                            if rTime.status_code != 200:
                                print(f"❌ Erreur création pointage tâche {taskID}: {rTime.status_code} {rTime.text}")
                            elif testing:
                                print(f"⏱️ Pointage ajouté task_id={taskID} user_id={userId}")
                        except Exception as e:
                            print(f"❌ Exception pointage tâche {taskID}:", e)

            except Exception as e:
                print(f"❌ Exception création tâche {i+1}:", e)

    return projectID


# --- Test unitaire ---
if __name__ == "__main__":
    for i in range(2):
        generate_project(
            dateCreate=fake.date_this_year(),
            nbTasks=3,
            nbtasksTime=3,
            retDataUser=fill_users(),
            retDataThirdParties=fill_thirdparties(),
            nbContactsMax=3,
            testing=True
        )
