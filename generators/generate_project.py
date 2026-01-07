import random
import requests
from datetime import timedelta
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from dolibarr_api import *
from utils import *

def generate_project(dateCreate, retDataUser, retDataThirdParties, testing=False):
    """
    Génère un projet avec tâches, contacts et pointages de manière sécurisée.
    Respecte le statut : draft / open / closed pour pointages.
    """

    urlProjects = urlBase + "projects/"
    urlTasks = urlBase + "tasks"

    dateCreateWithTime = dateCreate + timedelta(
        hours=random.randint(6, 19),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59)
    )

    dateStart = fake.date_time_between(start_date=dateCreate, end_date=dateCreate + timedelta(days=30))
    dateEnd = fake.date_time_between(start_date=dateStart, end_date=dateStart + timedelta(days=180))

    dateStartTs = int(dateStart.timestamp())
    dateEndTs = int(dateEnd.timestamp())

    # Projet draft/open/closed
    projectStatus = random.choice([0, 1, 2])

    dataProject = {
        "ref": "auto",
        "title": fake.catch_phrase(),
        "description": fake.text(200),
        "date_start": dateStartTs,
        "date_end": dateEndTs,
        "socid": get_random_client(retDataThirdParties),
        "usage_task": 1,
        "usage_bill_time": 0,
        "budget_amount": random.randint(500, 10000),
        "status": projectStatus,
        "public": 1
    }

    try:
        r = requests.post(urlProjects, headers=headers, json=dataProject)
        if r.status_code != 200:
            print(f"❌ Erreur création projet: {r.status_code} - {r.text}")
            return None
        projectID = get_created_id(r)
        if testing:
            print(f"✅ Projet créé ID={projectID}, statut={projectStatus}")
    except Exception as e:
        print("❌ Exception création projet:", e)
        return None

    # UPDATE POST-CREATION
    try:
        requests.put(
            urlProjects + str(projectID),
            headers=headers,
            json={
                "date_c": dateCreateWithTime.strftime("%Y-%m-%d %H:%M:%S"),
                "note_private": fake.text(200),
                "note_public": fake.text(200),
            }
        )
    except Exception as e:
        print("❌ Exception update projet:", e)

    # CONTACTS
    projectContacts = []
    urlProjectContacts = urlProjects + f"{projectID}/contacts"

    # Contacts internes (au moins 1 si max=0)
    internalMax = max(nbInternalContactMax, 1)
    for _ in range(random.randint(1, internalMax)):
        user = get_random_user(retDataUser)
        contact = {
            "fk_socpeople": user["id"],
            "type_contact": random.choice(["PROJECTLEADER", "PROJECTCONTRIBUTOR"]),
            "source": "internal"
        }
        try:
            r = requests.post(urlProjectContacts, headers=headers, json=contact)
            if r.status_code == 200:
                projectContacts.append(contact)
                if testing:
                    print(f"👤 Contact interne ajouté user_id={user['id']}")
            else:
                if testing:
                    print(f"❌ Erreur contact interne {user['id']}: {r.status_code} - {r.text}")
        except Exception as e:
            print("❌ Exception contact interne:", e)

    # Contacts externes
    for _ in range(random.randint(0, nbExternalContactMax)):
        socid = get_random_client(retDataThirdParties)
        socpeople = fill_socpeople(socid)
        if not socpeople:
            continue
        contact = {
            "fk_socpeople": random.choice(socpeople)["id"],
            "type_contact": "PROJECTCONTRIBUTOR",
            "source": "external"
        }
        try:
            r = requests.post(urlProjectContacts, headers=headers, json=contact)
            if r.status_code == 200 and testing:
                print(f"🌐 Contact externe ajouté socpeople_id={contact['fk_socpeople']}")
            elif r.status_code != 200:
                if testing:
                    print(f"❌ Erreur contact externe {contact['fk_socpeople']}: {r.status_code} - {r.text}")
        except Exception as e:
            print("❌ Exception contact externe:", e)

    # TÂCHES
    tasks_created = []
    for _ in range(random.randint(0, nbNewMaxTask)):
        taskStatus = random.choice([0,1,2])  # draft/open/closed
        dateTaskC = fake.date_time_between(dateCreate, dateEnd)
        dateTaskO = fake.date_time_between(dateTaskC, dateEnd)
        dateTaskE = fake.date_time_between(dateTaskO, dateEnd)
        task_data = {
            "ref": "auto",
            "fk_project": projectID,
            "label": fake.catch_phrase(),
            "description": fake.text(200),
            "date_start": int(dateTaskO.timestamp()),
            "date_end": int(dateTaskE.timestamp()),
            "planned_workload": random.randint(1,20)*3600,
            "status": taskStatus
        }
        try:
            r = requests.post(urlTasks, headers=headers, json=task_data)
            if r.status_code != 200:
                if testing:
                    print(f"❌ Erreur création tâche: {r.status_code} - {r.text}")
                continue
            taskID = get_created_id(r)
            tasks_created.append((taskID, taskStatus))
            if testing:
                print(f"📝 Tâche créée ID={taskID}, statut {taskStatus}")
        except Exception as e:
            print("❌ Exception création tâche:", e)
            continue

        # TASKEXECUTIVE internes
        internalContacts = [c for c in projectContacts if c["source"]=="internal"]
        for c in random.sample(internalContacts, min(len(internalContacts), random.randint(0,3))):
            try:
                r = requests.post(
                    urlBase + f"tasks/{taskID}/contacts",
                    headers=headers,
                    json={
                        "fk_socpeople": c["fk_socpeople"],
                        "type_contact": "TASKEXECUTIVE",
                        "source": "internal"
                    }
                )
                if r.status_code == 200 and testing:
                    print(f"✅ TASKEXECUTIVE affecté task_id={taskID} user_id={c['fk_socpeople']}")
                elif r.status_code != 200 and testing:
                    print(f"❌ Erreur affectation TASKEXECUTIVE: {r.status_code} - {r.text}")
            except Exception as e:
                print("❌ Exception TASKEXECUTIVE:", e)

    # POINTAGES
    for taskID, taskStatus in tasks_created:
        if taskStatus == 0:  # draft → skip
            if testing:
                print(f"⏩ Tâche {taskID} en draft → pointages skip")
            continue

        internalContacts = [c for c in projectContacts if c["source"]=="internal"]
        for _ in range(random.randint(1, nbNewMaxTaskTime)):
            if not internalContacts:
                continue
            userId = random.choice(internalContacts)["fk_socpeople"]
            pointage_data = {
                "date": fake.date_time_between(dateTaskO, dateTaskE).strftime("%Y-%m-%d %H:%M:%S"),
                "duration": random.randint(300,3600),
                "user_id": userId,
                "progress": random.randint(0,100),
                "note": fake.sentence(8)
            }
            try:
                r = requests.post(
                    urlBase + f"tasks/{taskID}/addtimespent",
                    headers=headers,
                    json=pointage_data
                )
                if r.status_code == 200 and testing:
                    print(f"⏱️ Pointage ajouté task_id={taskID} user_id={userId}")
                elif r.status_code != 200 and testing:
                    print(f"❌ Erreur ajout pointage task_id={taskID} user_id={userId}: {r.status_code} - {r.text}")
            except Exception as e:
                print("❌ Exception ajout pointage:", e)

        # update statut final task (si c'était draft, on le laisse, sinon on peut clôturer)
        if taskStatus != 0:
            try:
                r = requests.put(urlBase + f"tasks/{taskID}", headers=headers, json={"status":taskStatus})
                if r.status_code != 200 and testing:
                    print(f"❌ Erreur update statut task {taskID}: {r.status_code} - {r.text}")
            except Exception as e:
                print("❌ Exception update statut task:", e)

    # Clôture projet à la fin
    if projectStatus == 2:  # closed
        try:
            r = requests.put(urlProjects + str(projectID), headers=headers, json={"status":2})
            if r.status_code == 200 and testing:
                print(f"✅ Projet {projectID} clôturé")
            elif r.status_code != 200 and testing:
                print(f"❌ Erreur clôture projet {projectID}: {r.status_code} - {r.text}")
        except Exception as e:
            print("❌ Exception clôture projet:", e)

    if testing:
        print(f"🎉 Projet {projectID} génération terminée.")

    return projectID

# --- TEST UNITAIRE ---
if __name__ == "__main__":
    for i in range(2):
        print(generate_project(
            dateCreate = fake.date_this_year(),
            retDataUser = fill_users(),
            retDataThirdParties = fill_thirdparties('customer'),
            testing=True))
