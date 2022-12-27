from flask import Flask, jsonify, request, Response
from flask_cors import CORS
from flask_swagger_ui import get_swaggerui_blueprint
from pymongo import MongoClient
from bson import json_util
from bson.objectid import ObjectId
import json
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

# Initiate Flask application
app = Flask(__name__)
app.secret_key = "jurw07yhf0w87fv0d"

CORS(app)

# MongoDB config
cluster = "mongodb+srv://Admin:Dobcon2022@dobcon.udigbzh.mongodb.net/?retryWrites=true&w=majority"
client = MongoClient(cluster)
db = client['dobcon_licenses']  

# Swagger config
SWAGGER_URL = '/swagger'
API_URL = '/static/swagger.json'
SWAGGER_BLUEPRINT = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={
        'app_name': 'Licenses API'
    }
)
app.register_blueprint(SWAGGER_BLUEPRINT, url_prefix = SWAGGER_URL)

# API
@app.route('/', methods = ['GET'])
def index():
    msg = "<h1>Licenses API</h1>"
    return msg

@app.route('/licenses', methods=['GET'])
def get_licenses():
    licenses = db.licenses.find()
    response = json_util.dumps(licenses)
    return Response(response, mimetype='application/json')

@app.route('/get_purchase_history', methods=['GET'])
def get_purchase_history():
    history = db.purchase_history.find()
    response = json_util.dumps(history)
    return Response(response, mimetype='application/json')

# Create un-assigned licenses
# Dobcon internal ONLY
@app.route('/create_licenses', methods=['POST'])
def create_licenses():
    created_licenses = []
    buyer = request.json['buyer']
    buyer_email = request.json['buyer_email']
    company = request.json['company']
    no_licenses = request.json['number_licenses']
    license_type = request.json['license_type']
    # Set license expiration date
    tday = date.today()
    
    if(license_type == '1-year'):
        expiration_date = tday + relativedelta(years=1)
    elif(license_type == '2-year'):
        expiration_date = tday + relativedelta(years=2)
    else:
        expiration_date = tday + relativedelta(months=+3)

    if buyer and buyer_email and company and no_licenses and license_type: 
        company = company.lower().replace(' ','_')
        # Create x licenses with the name of the company
        for _ in range(no_licenses):
            license = db.licenses.insert_one({
                'name':'',
                'company':company, 
                'username':'', 
                'email':'', 
                'pc_device':'', 
                'mob_device':'',
                'role':'',
                'department':'',
                'status': 'active',
                'license_type':license_type,
                'creation_date':str(tday),
                'expiration_date':str(expiration_date)
            }) 
            created_licenses.append(str(license.inserted_id))
        response = json.dumps(created_licenses)
        db.purchase_history.insert_one({
            'company':company,
            'licenses': no_licenses,
            'buyer': buyer,
            'buyer_email':buyer_email
        })
        return jsonify(response)

@app.route('/create_admin', methods=['POST'])
def create_admin():
    company = "dobcon"
    name = request.json["name"]
    email = request.json['email']
    role = request.json['role']
    license = db.licenses.insert_one({
        'name': name,
        'company': company,
        'username': email,
        'email': email,
        'pc_device':'any',
        'mob_device':'any',
        'role': role,
        'status':'active'
    })
    print(license)
    response = {'Created Admin license': str(license.inserted_id)}
    return response

@app.route('/get_device/<username>', methods = ['GET'])
def get_device(username):
    lic = db.licenses.find_one({'username':username})
    if lic:
        device = lic['pc_device']
        response = {'pc_device' : device}
    else:
        response = {'Error message':'User not found'}
    return response

@app.route('/get_available_licenses/<company>', methods = ['GET'])
def get_available_licenses(company):
    company = company.lower().replace(' ','_')
    available_lic = db.licenses.count_documents({'company':company, 'username':''})
    response = {'available_licenses' : available_lic}
    return response

@app.route('/register_device', methods = ['PUT'])
def register_device():
    username = request.json['username']
    lic = db.licenses.find_one({'username':username})
    if lic:
        lic_id = lic['_id']
        if request.json['pc_device']:
            pc_dev = request.json['pc_device']
            db.licenses.update_one({'_id': ObjectId(lic_id)}, {'$set': {
                'pc_device': pc_dev
            }})
        #if request.json['mob_device']:
            #mob_dev = request.json['mob_device']
            #db.licenses.update_one({'_id': ObjectId(lic)}, {'$set': {
                #'mob_device': mob_dev
            #}})
        response = {'device has been successfully linked to ' : str(lic_id)}
    else:
        response = {'Error message':'User not found'}
    return response

@app.route('/check_device', methods = ['POST'])
def check_device():
    email = request.json['email']
    pc_current_dev = request.json['pc_device']
    lic = db.licenses.find_one({'email':email})
    if lic:
        lic_id = lic['_id']
        pc_dev = lic['pc_device']
        lic_status = lic['status']
        if (pc_dev == 'any'):
            response = {"Device check result":"deviceConfirmed"}
            return response

        if (pc_dev == ''):
            db.licenses.update_one({'_id': ObjectId(lic_id)}, {'$set': {
            'pc_device': pc_current_dev
            }})
            response = {"Device check result":"deviceConfirmed"}
        elif (pc_dev == pc_current_dev):
            if (lic_status == 'active'):      
                expirationDate = lic['expiration_date']
                expirationDate = datetime.strptime(expirationDate, "%Y-%m-%d").date()
                today = date.today()
                print(expirationDate)
                print(today)
                if(today < expirationDate):
                    response = {"Device check result":"deviceConfirmed", "License Status":lic_status}
                else:
                    lic_status = 'not-active'
                    db.licenses.update_one({'_id': ObjectId(lic_id)}, {'$set': {
                    'status': lic_status
                    }})
                    response = {"Device check result":"deviceNotConfirmed", "License Status":lic_status}
            else:
                response = {"Device check result":"licenseNotActive"}
        else:
            response = {"Device check result":"incorrectDevice"}
    else:
        response = {"Device check result":"User not found"}
    return response


# Super User assigns each license
@app.route('/assign_license', methods = ['PUT'])
def assign_license():
    name = request.json['name']
    company = request.json['company']
    company = company.lower().replace(' ','_')
    empty_license = db.licenses.find_one({'company':company, 'username':''})
    email = request.json['email']
    role = request.json['role']
    department = request.json['department']
    if empty_license:
        if name and email and role:
            empty_id = empty_license['_id']
            db.licenses.update_one({'_id': empty_id}, {'$set': {
                'name': name,
                'username': email,
                'email': email,
                'role': role,
                'department': department
            }})
            response = {'assigned user':email, 'assigned license':str(empty_id)}
        else:
            response = 'information is not complete'
    else:
        response = {'response message':'no available license for '+ company}
    return response

@app.route('/reassign_license', methods = ['PUT'])
def reassign_license():
    name = request.json['name']
    old_username = request.json['old_username']
    company = request.json['company']
    company = company.lower().replace(' ','_')
    email = request.json['email']
    role = request.json['role']
    department = request.json['department']
    lic = db.licenses.find_one({'username':old_username})
    lic_id = lic['_id']
    db.licenses.update_one({'_id': lic_id}, {'$set': {
        'name': name,
        'username': email,
        'email': email,
        'pc_device':'',
        'mob_device':'',
        'role': role,
        'department': department
    }})
    response = {'license reassigned to':email, 'assigned license':str(lic_id)}
    return response

@app.route('/change_username', methods=['PUT'])
def chage_username():
    old_username = request.json['old_username']
    new_username = request.json['new_username']
    lic = db.licenses.find_one({'username':old_username})
    if lic:
        lic_id = lic['_id']
        db.licenses.update_one({'_id': lic_id}, {'$set': {
            'username': new_username
        }})
        response = {'Updated username':new_username, 'assigned license':str(lic_id)}
    else:
        response = {'Updated username':None, "assigned license":None}
    return response


@app.route('/renew_license', methods = ['PUT'])
def renew_license():
    username = request.json['username']
    lic = db.licenses.find_one({'username':username})
    if lic:
        lic_id = lic['_id']
        tday = date.today()
        expiration = lic['expiration_date']
        expirationDate = datetime.strptime(expiration, "%Y-%m-%d").date()
        if tday > expirationDate:
            expiration_date = tday + relativedelta(years=2)
        else:
            expiration_date = expirationDate + relativedelta(years=2) 
        lic_status = 'active'
        db.licenses.update_one({'_id': ObjectId(lic_id)}, {'$set': {
            'status': lic_status,
            'expiration_date':str(expiration_date)
        }})
        response = {"New expiration date":str(expiration_date)}
    else:
        response = {"Error message":"user not found"}
    return response
    
@app.route('/company_licenses/<company>', methods = ['GET'])
def company_licenses(company):
    company = company.lower().replace(' ','_')
    data = []
    cursor = list(db.licenses.find({'company':company}))
    if cursor:
        for license in cursor:
            if license['username'] != '':
                license['_id'] = str(license['_id'])
                data.append(license)
        response = data
    else:
        response = "Company: " + company + " not found."
    return jsonify(response)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

