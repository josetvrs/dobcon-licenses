from crypt import methods
from flask import Flask, jsonify, request, Response, session
from flask_restful import Resource, Api
from flask_cors import CORS
from pymongo import MongoClient
from bson import json_util
from bson.objectid import ObjectId
import json
from datetime import date, datetime

# Flask application
app = Flask(__name__)
app.secret_key = "jurw07yhf0w87fv0d"
#api = Api(app)
CORS(app)

# Mongo configuration
cluster = "mongodb+srv://dobcon-adm:d68A7g77mWjmamWK@dobcon.vnaug.mongodb.net/?retryWrites=true&w=majority"
client = MongoClient(cluster)
db = client['dobcon_db']    

@app.route('/', methods = ['GET'])
def index():
    msg = "<h1>Hello World</h1>"
    return msg

@app.route('/licenses', methods=['GET'])
def get_licenses():
    licenses = db.dobcon_licenses.find()
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
    if(license_type == 'demo'):
        expiration_date = tday.replace(month = tday.month + 3)
    else:
        expiration_date = tday.replace(year = tday.year + 1)

    if buyer and buyer_email and company and no_licenses and license_type: 
        company = company.lower().replace(' ','_')
        # Create x licenses with the name of the company
        for _ in range(no_licenses):
            license = db.dobcon_licenses.insert_one({
                'company':company, 
                'username':'', 
                'email':'', 
                'pc_device':'', 
                'mob_device':'',
                'role':'',
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
    username = request.json['username']
    email = request.json['email']
    role = request.json['role']
    license = db.dobcon_licenses.insert_one({
        'company': company,
        'username': username,
        'email': email,
        'pc_device':'any',
        'mob_device':'any',
        'role': role,
        'status':'active'
    })
    print(license)
    response = {'Created Admin license': str(license)}
    return response

@app.route('/get_device', methods = ['GET'])
def get_device():
    username = request.json['username']
    lic = db.dobcon_licenses.find_one({'username':username})
    device = lic['pc_device']
    response = {'pc_device' : device}
    return response

@app.route('/get_available_licenses/<company>', methods = ['GET'])
def get_available_licenses(company):
    company = company.lower().replace(' ','_')
    available_lic = db.dobcon_licenses.count_documents({'company':company, 'username':''})
    response = {'available_licenses' : available_lic}
    return response

@app.route('/register_device', methods = ['PUT'])
def register_device():
    username = request.json['username']
    lic = db.dobcon_licenses.find_one({'username':username})
    lic_id = lic['_id']
    if request.json['pc_device']:
        pc_dev = request.json['pc_device']
        db.dobcon_licenses.update_one({'_id': ObjectId(lic_id)}, {'$set': {
            'pc_device': pc_dev
        }})
    #if request.json['mob_device']:
        #mob_dev = request.json['mob_device']
        #db.dobcon_licenses.update_one({'_id': ObjectId(lic)}, {'$set': {
            #'mob_device': mob_dev
        #}})
    response = {'device has been successfully assigned to ' : str(lic_id)}
    return response

@app.route('/check_device', methods = ['POST'])
def check_device():
    email = request.json['email']
    pc_current_dev = request.json['pc_device']

    lic = db.dobcon_licenses.find_one({'email':email})
    if lic:
        lic_id = lic['_id']
        pc_dev = lic['pc_device']
        lic_status = lic['status']
        if (pc_dev == 'any'):
            response = {"Device check result":"deviceConfirmed"}
            return response

        if (pc_dev == ''):
            db.dobcon_licenses.update_one({'_id': ObjectId(lic_id)}, {'$set': {
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
                    db.dobcon_licenses.update_one({'_id': ObjectId(lic_id)}, {'$set': {
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
    company = request.json['company']
    company = company.lower().replace(' ','_')
    empty_license = db.dobcon_licenses.find_one({'company':company, 'username':''})
    username = request.json['username']
    email = request.json['email']
    role = request.json['role']
    if empty_license:
        if username and email and role:
            empty_id = empty_license['_id']
            db.dobcon_licenses.update_one({'_id': empty_id}, {'$set': {
                'username': username,
                'email': email,
                'role': role
            }})
            response = {'assigned user':username, 'assigned license':str(empty_id)}
        else:
            response = 'information is not complete'
    else:
        response = {'response message':'no available license for '+ company}
    return response

@app.route('/reassign_license', methods = ['PUT'])
def reassign_license():
    old_username = request.json['old_username']
    company = request.json['company']
    company = company.lower().replace(' ','_')
    username = request.json['username']
    email = request.json['email']
    role = request.json['role']
    lic = db.dobcon_licenses.find_one({'username':old_username})
    lic_id = lic['_id']
    db.dobcon_licenses.update_one({'_id': lic_id}, {'$set': {
        'username': username,
        'email': email,
        'pc_device':'',
        'mob_device':'',
        'role': role
    }})
    response = {'license reassigned to':username, 'assigned license':str(lic_id)}
    return response

@app.route('/change_username', methods=['PUT'])
def chage_username():
    old_username = request.json['old_username']
    new_username = request.json['new_username']
    lic = db.dobcon_licenses.find_one({'username':old_username})
    lic_id = lic['_id']
    db.dobcon_licenses.update_one({'_id': lic_id}, {'$set': {
        'username': new_username
    }})
    response = {'Updated username':new_username, 'assigned license':str(lic_id)}
    return response


@app.route('/renew_license', methods = ['PUT'])
def renew_license():
    username = request.json['username']
    lic = db.dobcon_licenses.find_one({'username':username})
    lic_id = lic['_id']
    tday = date.today()
    expiration_date = tday.replace(year = tday.year + 1)
    lic_status = 'active'
    db.dobcon_licenses.update_one({'_id': ObjectId(lic_id)}, {'$set': {
        'status': lic_status,
        'expitation_date':str(expiration_date)
    }})
    response = {"License Status":lic_status}
    return response
    

@app.route('/company_licenses/<company>', methods = ['GET'])
def company_licenses(company):
    company = company.lower().replace(' ','_')
    data = []
    cursor = list(db.dobcon_licenses.find({'company':company}))
    for license in cursor:
        if license['username'] != '':
            license['_id'] = str(license['_id'])
            data.append(license)
    return jsonify(data)

# Remove all licenses in collection (FOR TEST ONLY)
@app.route('/remove_all', methods=['GET'])
def remove_all():
    db.dobcon_licenses.delete_many({})
    response = "licenses delted"
    return response

if __name__ == "__main__":
    app.run(debug=True)

