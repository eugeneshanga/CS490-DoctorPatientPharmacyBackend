## Smart Eatz Pharmacy Backend

### Prerequisites
- python

### Getting Started

Clone Repo

HTTPs

`git clone https://github.com/eugeneshanga/CS490-DoctorPatientPharmacyBackend.git`

SSH

`git clone git@github.com:eugeneshanga/CS490-DoctorPatientPharmacyBackend.git`

Create the Virtual Environment(Optional but recommended)

`python3 -m venv venv`

Activate the venv

Ubuntu/Mac
`source venv/bin/activate`

Windows
`venv\Scripts\activate`

Install Flask

`pip install flask`

Install Dependencies

`pip install flask-cors`
`pip install mysql-connector-python`
`pip install -r requirements.txt`

### Repo Organization (Updated: Nick on 3/16)

- `.github/` - contains CI workflows
- `blueprints/` - contains python/flask endpoint files
- `database/` - Contains database schema and mock data
- `.flake8` - config for flake8 linter - see lint doc for more details
- `.gitignore` - self explanatory google if confused
- `README.md` - The file you are ready now
- `app.py` - Basically our `main` file. Starts the project, registers the blueprints
- `package.json` - this is for semantic release, not rlly sure if we will use it or not


### View the docs folder for more information