from flask import Flask, render_template, url_for, request, redirect
from flask_mail import Mail, Message
from search import Search, load, update_json
from sheetgenerator import generate_report, generate_reports
from muncypdf import pdf_gen, forklift1, depth_micrometer, inside_micrometer, outside_micrometer, fire_protection
import pandas as pd
import csv
import json
import itertools
import os
from datetime import date
import requests
import shutil
import threading
import time
import uuid
from datetime import datetime
import firebase_admin
import webbrowser
from firebase_admin import credentials
from firebase_admin import firestore
#from firebase_admin import auth
from flask import send_file, send_from_directory
import pyrebase
import zipfile

from flask_login import current_user

import mysql.connector
import sys
import boto3

firebaseConfig = {
    "apiKey": "AIzaSyAx_91UhqLyQM9BwTf2hhwUC-1T6DNV0RY",
    "authDomain": "mycloud-d0d74.firebaseapp.com",
    "databaseURL": "https://mycloud-d0d74.firebaseio.com",
    "projectId": "mycloud-d0d74",
    "storageBucket": "mycloud-d0d74.appspot.com",
    "messagingSenderId": "887766660646",
    "appId": "1:887766660646:web:a23f6afeeca7c4ca0fd8e7",
    "measurementId": "G-G7HPD5ZDYM"
  }

app = Flask(__name__)

mail= Mail(app)

app.config['MAIL_SERVER']='smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = 'muncycloud@gmail.com'
app.config['MAIL_PASSWORD'] = 'MuncyCloud@5820'
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
mail = Mail(app)

cred = credentials.Certificate('/Users/gunam/Downloads/mycloud-d0d74-firebase-adminsdk-xuf9c-f6faa91a17.json')
firebase_admin.initialize_app(cred)

db = firestore.client()

firebase  = pyrebase.initialize_app(firebaseConfig)
auth = firebase.auth()
user = ""


ENDPOINT="cumuluscloud.c3mqraooeeu8.us-east-2.rds.amazonaws.com"
PORT="3306"
USR="admin"
REGION="us-east-2a"
DBNAME="muncycloud"
token ="sherlock"
os.environ['LIBMYSQL_ENABLE_CLEARTEXT_PLUGIN'] = '1'
client = boto3.client('rds', region_name="us-east-2a")

@app.before_first_request
def activate_job():
    def run_job():
        while True:
            #print("Run recurring task")
            today = date.today()
            d1 = today.strftime("%Y-%m-%d")
            conn =  mysql.connector.connect(host=ENDPOINT, user=USR, passwd=token, port=PORT, database=DBNAME)
            cur = conn.cursor()
            command = """SELECT * FROM REMINDERS"""
            cur.execute(command)
            rr = cur.fetchall()
            result1 = len(rr)
            if result1 > 0:
                desc = cur.description
                column_names = [col[0] for col in desc]
                data = [dict(zip(column_names, row))for row in rr]
                conn.commit()
                conn.close()
            y = data
            for row in y:
                check_date = datetime.strptime(str(row['ALERT_DATE']),'%Y-%m-%d').strftime('%Y-%m-%d')
                if row['SENT_STATUS'] == "False" and check_date==d1:
                    #print("sending email")
                    subject = row['EMAIL_SUBJECT']
                    customername = row['CUSTOMER_NAME']
                    assetno = row['ASSETNO']
                    message = row['EMAIL_MESSAGE']
                    recipients = row['EMAIL_ID']
                    alertdate = row['ALERT_DATE']
                    body = str(row['CUSTOMER_NAME'])+"\t"+str(row['ASSETNO'])+"\n"+str(row['EMAIL_MESSAGE'])
                    conn =  mysql.connector.connect(host=ENDPOINT, user=USR, passwd=token, port=PORT, database=DBNAME)
                    cur = conn.cursor()
                    command = """UPDATE REMINDERS SET SENT_STATUS = 'True' WHERE CUSTOMER_NAME = %s AND ASSETNO = %s AND ALERT_DATE = %s AND EMAIL_ID = %s AND EMAIL_MESSAGE = %s AND EMAIL_SUBJECT = %s """
                    cur.execute(command,(customername,assetno,alertdate,recipients,message, subject))
                    conn.commit()
                    conn.close()
                    with app.app_context():
                        print("sending mail")
                        msg = Message(subject, sender = 'muncycloud@gmail.com', recipients = [recipients])
                        msg.body = body
                        mail.send(msg)
                        print("email sent")
                    #return "Sent"
            time.sleep(3)

    thread = threading.Thread(target=run_job)
    thread.start()

def start_runner():
    def start_loop():
        not_started = True
        while not_started:
            print('In start loop')
            try:
                r = requests.get('http://3.128.242.225/')
                if r.status_code == 200:
                    print('Server started, quiting start_loop')
                    not_started = False
                print(r.status_code)
            except:
                print('Server not yet started')
            time.sleep(2)

    print('Started runner')
    thread = threading.Thread(target=start_loop)
    thread.start()


@app.route('/', methods =['POST','GET'])
def login():
    if request.method == "POST":
        name = request.form['username']
        password = request.form['pass']
        try:
            if(auth.sign_in_with_email_and_password(name,password)):
                return render_template("home.html")
        except:
            return render_template('index.html')
    else:
        return render_template('index.html')


@app.route('/home', methods=['GET','POST'])
def home():
    if request.method == 'POST':
        return render_template('home.html')
    else:
        return render_template('home.html')



@app.route('/alerts', methods=['GET','POST'])
def alerts():
    if request.method == 'POST':
        email = request.form['email']
        assetno = request.form['assetnumber']
        customername = request.form['customername']
        date = request.form['inspectiondate']
        date = datetime.strptime(date,'%Y-%m-%d').strftime('%Y/%m/%d')
        subject = request.form['subject']
        message = request.form['message']

        if 'reset' in request.form:
            return render_template('alerts.html')

        elif 'save' in request.form:
            print("send email")
            formid = str(uuid.uuid4()).replace('-','')
            sent= "False"
            conn =  mysql.connector.connect(host=ENDPOINT, user=USR, passwd=token, port=PORT, database=DBNAME)
            cur = conn.cursor()
            command = """INSERT INTO REMINDERS (FORMID , ASSETNO, CUSTOMER_NAME, ALERT_DATE, EMAIL_ID, EMAIL_MESSAGE, EMAIL_SUBJECT, SENT_STATUS) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""
            cur.execute(command,(formid, assetno, customername, date, email, message, subject, sent))
            # desc = cur.description
            # column_names = [col[0] for col in desc]
            # data = [dict(zip(column_names, row))for row in cur.fetchall()]
            conn.commit()
            conn.close()

            # for doc in data:
            #     if doc['SENT_STATUS'] == "True":
            #         doc['SENT_STATUS'] = "SENT"
            #     else:
            #         doc['SENT_STATUS'] = "NOT YET"
            #     results.append(doc)
            # y = results
            return json.dumps({'success':True}), 200, {'ContentType':'application/json'}
            #return render_template('alerts.html',email=email,assetnumber=assetno,customername=customername,inspectiondate=date,subject=subject,message=message ,y=y)
        elif 'reload' in request.form:
            print("alert reload")
            results=[]
            conn =  mysql.connector.connect(host=ENDPOINT, user=USR, passwd=token, port=PORT, database=DBNAME)
            cur = conn.cursor()
            command = """SELECT * FROM REMINDERS"""
            cur.execute(command)
            rr = cur.fetchall()
            result1 = len(rr)
            if result1 > 0:
                desc = cur.description
                column_names = [col[0] for col in desc]
                data = [dict(zip(column_names, row))for row in rr]
                conn.commit()
                conn.close()
            y = data
            return render_template('alerts.html', y=y)

        else:
            print("post reload")
            return render_template('alerts.html')
            pass
    else:
        print("alert reload")
        results=[]
        conn =  mysql.connector.connect(host=ENDPOINT, user=USR, passwd=token, port=PORT, database=DBNAME)
        cur = conn.cursor()
        command = """SELECT * FROM REMINDERS"""
        cur.execute(command)
        rr = cur.fetchall()
        result1 = len(rr)
        if result1 > 0:
            desc = cur.description
            column_names = [col[0] for col in desc]
            data = [dict(zip(column_names, row))for row in rr]
            conn.commit()
            conn.close()

        for row in data:
            if row['SENT_STATUS'] == "True":
                row['SENT_STATUS'] = "SENT"
            else:
                row['SENT_STATUS'] = "NOT SENT"
            row['ALERT_DATE'] = datetime.strptime(str(row['ALERT_DATE']),'%Y-%m-%d').strftime('%Y-%m-%d')
        y = data
        return render_template('alerts.html', y=y)


@app.route('/contacts', methods=['GET','POST'])
def contacts():
    print('contacts')
    if request.method == 'POST':
        if 'home' in request.form:
            return render_template('home.html')
        else:
            return render_template('contacts.html')
    else:
        return render_template('contacts.html')



@app.route("/search", methods =["POST","GET"])
def search():
    if request.method == "POST":
        # user = auth.get_user_by_email(email)
        # print('Successfully fetched user data: {0}'.format(user.uid))
        results=[]
        email = request.args.get('emailid', default='', type=str)
        print(email)
        assetno = request.form['assetnumber']
        customername = request.form['customername']
        fromdate = request.form['fromdate']
        todate = request.form['todate']
        from_duedate = request.form['from_duedate']
        to_duedate = request.form['to_duedate']
        if from_duedate == "" and to_duedate == "":
            b = fromdate
            c = todate
        if fromdate == "" and todate == "":
            b = from_duedate
            c = to_duedate
        location = request.form['location']
        producttype = request.form['producttype']
        inspectiontype = request.form['inspectiontype']
        result = request.form['result']
        ano = request.form['assetnumber']
        cname = request.form['customername']
        loc = request.form['location']
        op = request.form['operator']
        insp_type = request.form['inspectiontype']
        prod = producttype
        select_1 = ""
        select_2 =""
        select_3 =""
        select_4 =""
        if result == "":
            select_1 = "selected"
            result=""

        elif result == "PASS":
            select_2 = "selected"

        elif result == "FAIL":
            select_3 = "selected"

        elif result == "REPAIR":
            select_4 = "selected"

        else:
            select_5 = "selected"

        if "search" in request.form and fromdate == "" and todate== "" :
            print("due date")
            try:
                b = datetime.strptime(b,'%Y-%m-%d').strftime('%Y-%m-%d')
                c = datetime.strptime(c,'%Y-%m-%d').strftime('%Y-%m-%d')
                conn =  mysql.connector.connect(host=ENDPOINT, user=USR, passwd=token, port=PORT, database=DBNAME)
                cur = conn.cursor()
                command = """SELECT * FROM INSPECTIONS WHERE DUE_DATE <= %s AND DUE_DATE >= %s ORDER BY STR_TO_DATE(DUE_DATE, '%y-%m-%d')"""
                cur.execute(command,(c,b))
                desc = cur.description
                column_names = [col[0] for col in desc]
                data = [dict(zip(column_names, row))for row in cur.fetchall()]
                conn.commit()
                conn.close()
                #print(data)
                return render_template('search.html', assetnumber=assetno, customername=customername, fromdate=fromdate, todate=todate, location=location, tbl=data, y=data, operator=op, select_1 = select_1,select_2 = select_2,select_3 = select_3,select_4 = select_4, inspectiontype=insp_type, producttype=prod, from_duedate =from_duedate, to_duedate=to_duedate)
                #return json.dumps({'success':True}), 200, {'ContentType':'application/json'}
            except Exception as e:
                #return json.dumps({'success':False}), 200, {'ContentType':'application/json'}
                print("Database connection failed due to {}".format(e))
                data=[]
                return render_template('search.html', assetnumber=assetno, customername=customername, fromdate=fromdate, todate=todate, location=location, tbl=data, y=data, operator=op, select_1 = select_1,select_2 = select_2,select_3 = select_3,select_4 = select_4, inspectiontype=insp_type, producttype=prod, from_duedate=from_duedate, to_duedate=to_duedate)

        elif "search" in request.form and from_duedate == "" and to_duedate == "":
            print('search')
            try:
                b = datetime.strptime(b,'%Y-%m-%d').strftime('%Y-%m-%d')
                c = datetime.strptime(c,'%Y-%m-%d').strftime('%Y-%m-%d')
                ano = request.form['assetnumber']
                cname = request.form['customername']
                loc = request.form['location']
                op = request.form['operator']
                insp_type = request.form['inspectiontype']
                prod = producttype

                conn =  mysql.connector.connect(host=ENDPOINT, user=USR, passwd=token, port=PORT, database=DBNAME)
                cur = conn.cursor()

                if prod=="" and insp_type=="" and op=="" and cname =="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b))
                elif prod=="" and insp_type=="" and op=="" and cname =="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result))
                elif prod=="" and insp_type=="" and op=="" and cname =="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc))
                elif prod=="" and insp_type=="" and op=="" and cname =="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result))

                elif prod=="" and insp_type=="" and op=="" and cname =="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano))
                elif prod=="" and insp_type=="" and op=="" and cname =="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano))
                elif prod=="" and insp_type=="" and op=="" and cname =="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano))
                elif prod=="" and insp_type=="" and op=="" and cname =="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano))

                elif prod=="" and insp_type=="" and op=="" and cname !="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND CUSTOMER_NAME = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,cname))
                elif prod=="" and insp_type=="" and op=="" and cname !="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND CUSTOMER_NAME = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,cname))
                elif prod=="" and insp_type=="" and op=="" and cname !="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND CUSTOMER_NAME = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,cname))
                elif prod=="" and insp_type=="" and op=="" and cname !="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND CUSTOMER_NAME = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,cname))

                elif prod=="" and insp_type=="" and op=="" and cname !="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s AND CUSTOMER_NAME = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,cname))
                elif prod=="" and insp_type=="" and op=="" and cname !="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,cname))
                elif prod=="" and insp_type=="" and op=="" and cname !="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,cname))
                elif prod=="" and insp_type=="" and op=="" and cname !="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,cname))

                elif prod=="" and insp_type=="" and op!="" and cname =="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s  AND INSPECTOR = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,op))
                elif prod=="" and insp_type=="" and op!="" and cname =="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s  AND INSPECTOR = %s  ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,op))
                elif prod=="" and insp_type=="" and op!="" and cname =="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s  AND INSPECTOR = %s  ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,op))
                elif prod=="" and insp_type=="" and op!="" and cname =="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s  AND INSPECTOR = %s  ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,op))

                elif prod=="" and insp_type=="" and op!="" and cname =="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s  AND INSPECTOR = %s  ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,op))
                elif prod=="" and insp_type=="" and op!="" and cname =="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s  AND INSPECTOR = %s  ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,op))
                elif prod=="" and insp_type=="" and op!="" and cname =="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s  AND INSPECTOR = %s  ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,op))
                elif prod=="" and insp_type=="" and op!="" and cname =="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s  AND INSPECTOR = %s  ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,op))

                elif prod=="" and insp_type=="" and op!="" and cname !="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,cname,op))
                elif prod=="" and insp_type=="" and op!="" and cname !="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,cname,op))
                elif prod=="" and insp_type=="" and op!="" and cname !="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,cname,op))
                elif prod=="" and insp_type=="" and op!="" and cname !="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,cname,op))

                elif prod=="" and insp_type=="" and op!="" and cname !="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,cname,op))
                elif prod=="" and insp_type=="" and op!="" and cname !="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,cname,op))
                elif prod=="" and insp_type=="" and op!="" and cname !="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,cname,op))
                elif prod=="" and insp_type=="" and op!="" and cname !="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,cname,op))

                    ####################
                elif prod=="" and insp_type!="" and op=="" and cname =="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s  AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,insp_type))
                elif prod=="" and insp_type!="" and op=="" and cname =="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,insp_type))
                elif prod=="" and insp_type!="" and op=="" and cname =="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,insp_type))
                elif prod=="" and insp_type!="" and op=="" and cname =="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,insp_type))

                elif prod=="" and insp_type!="" and op=="" and cname =="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,insp_type))
                elif prod=="" and insp_type!="" and op=="" and cname =="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,insp_type))
                elif prod=="" and insp_type!="" and op=="" and cname =="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,insp_type))
                elif prod=="" and insp_type!="" and op=="" and cname =="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,insp_type))

                elif prod=="" and insp_type!="" and op=="" and cname !="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,cname,insp_type))
                elif prod=="" and insp_type!="" and op=="" and cname !="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,cname,insp_type))
                elif prod=="" and insp_type!="" and op=="" and cname !="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,cname,insp_type))
                elif prod=="" and insp_type!="" and op=="" and cname !="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,cname,insp_type))

                elif prod=="" and insp_type!="" and op=="" and cname !="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,cname,insp_type))
                elif prod=="" and insp_type!="" and op=="" and cname !="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,cname,insp_type))
                elif prod=="" and insp_type!="" and op=="" and cname !="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,cname,insp_type))
                elif prod=="" and insp_type!="" and op=="" and cname !="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,cname,insp_type))

                elif prod=="" and insp_type!="" and op!="" and cname =="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s  AND INSPECTOR = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,op,insp_type))
                elif prod=="" and insp_type!="" and op!="" and cname =="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,op,insp_type))
                elif prod=="" and insp_type!="" and op!="" and cname =="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,op,insp_type))
                elif prod=="" and insp_type!="" and op!="" and cname =="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,op,insp_type))

                elif prod=="" and insp_type!="" and op!="" and cname =="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,op,insp_type))
                elif prod=="" and insp_type!="" and op!="" and cname =="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,op,insp_type))
                elif prod=="" and insp_type!="" and op!="" and cname =="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,op,insp_type))
                elif prod=="" and insp_type!="" and op!="" and cname =="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,op,insp_type))

                elif prod=="" and insp_type!="" and op!="" and cname !="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,cname,op,insp_type))
                elif prod=="" and insp_type!="" and op!="" and cname !="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,cname,op,insp_type))
                elif prod=="" and insp_type!="" and op!="" and cname !="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,cname,op,insp_type))
                elif prod=="" and insp_type!="" and op!="" and cname !="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,cname,op,insp_type))

                elif prod=="" and insp_type!="" and op!="" and cname !="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,cname,op,insp_type))
                elif prod=="" and insp_type!="" and op!="" and cname !="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,cname,op,insp_type))
                elif prod=="" and insp_type!="" and op!="" and cname !="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,cname,op,insp_type))
                elif prod=="" and insp_type!="" and op!="" and cname !="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,cname,op,insp_type))

                ############################
                #######################################
                ####### PRODUCT NOT EMPTY

                elif prod!="" and insp_type=="" and op=="" and cname =="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s  AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,prod))
                elif prod!="" and insp_type=="" and op=="" and cname =="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,prod))
                elif prod!="" and insp_type=="" and op=="" and cname =="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,prod))
                elif prod!="" and insp_type=="" and op=="" and cname =="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,prod))

                elif prod!="" and insp_type=="" and op=="" and cname =="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,prod))
                elif prod!="" and insp_type=="" and op=="" and cname =="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,prod))
                elif prod!="" and insp_type=="" and op=="" and cname =="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,prod))
                elif prod!="" and insp_type=="" and op=="" and cname =="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,prod))

                elif prod!="" and insp_type=="" and op=="" and cname !="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND CUSTOMER_NAME = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,cname,prod))
                elif prod!="" and insp_type=="" and op=="" and cname !="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND CUSTOMER_NAME = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,cname,prod))
                elif prod!="" and insp_type=="" and op=="" and cname !="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND CUSTOMER_NAME = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,cname,prod))
                elif prod!="" and insp_type=="" and op=="" and cname !="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND CUSTOMER_NAME = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,cname,prod))

                elif prod!="" and insp_type=="" and op=="" and cname !="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,cname,prod))
                elif prod!="" and insp_type=="" and op=="" and cname !="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,cname,prod))
                elif prod!="" and insp_type=="" and op=="" and cname !="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,cname,prod))
                elif prod!="" and insp_type=="" and op=="" and cname !="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,cname,prod))

                elif prod!="" and insp_type=="" and op!="" and cname =="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s  AND INSPECTOR = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,op,prod))
                elif prod!="" and insp_type=="" and op!="" and cname =="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s  AND INSPECTOR = %s  AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,op,prod))
                elif prod!="" and insp_type=="" and op!="" and cname =="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s  AND INSPECTOR = %s  AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,op,prod))
                elif prod!="" and insp_type=="" and op!="" and cname =="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s  AND INSPECTOR = %s  AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,op,prod))

                elif prod!="" and insp_type=="" and op!="" and cname =="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s  AND INSPECTOR = %s  AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,op,prod))
                elif prod!="" and insp_type=="" and op!="" and cname =="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s  AND INSPECTOR = %s  AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,op,prod))
                elif prod!="" and insp_type=="" and op!="" and cname =="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s  AND INSPECTOR = %s  AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,op,prod))
                elif prod!="" and insp_type=="" and op!="" and cname =="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s  AND INSPECTOR = %s  AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,op,prod))

                elif prod!="" and insp_type=="" and op!="" and cname !="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,cname,op,prod))
                elif prod!="" and insp_type=="" and op!="" and cname !="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,cname,op,prod))
                elif prod!="" and insp_type=="" and op!="" and cname !="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,cname,op,prod))
                elif prod!="" and insp_type=="" and op!="" and cname !="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,cname,op,prod))

                elif prod!="" and insp_type=="" and op!="" and cname !="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,cname,op,prod))
                elif prod!="" and insp_type=="" and op!="" and cname !="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,cname,op,prod))
                elif prod!="" and insp_type=="" and op!="" and cname !="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,cname,op,prod))
                elif prod!="" and insp_type=="" and op!="" and cname !="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,cname,op,prod))

                    ####################
                elif prod!="" and insp_type!="" and op=="" and cname =="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s  AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,insp_type,prod))
                elif prod!="" and insp_type!="" and op=="" and cname =="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,insp_type,prod))
                elif prod!="" and insp_type!="" and op=="" and cname =="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,insp_type,prod))
                elif prod!="" and insp_type!="" and op=="" and cname =="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,insp_type,prod))

                elif prod!="" and insp_type!="" and op=="" and cname =="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,insp_type,prod))
                elif prod!="" and insp_type!="" and op=="" and cname =="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,insp_type,prod))
                elif prod!="" and insp_type!="" and op=="" and cname =="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,insp_type,prod))
                elif prod!="" and insp_type!="" and op=="" and cname =="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,insp_type,prod))

                elif prod!="" and insp_type!="" and op=="" and cname !="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,cname,insp_type,prod))
                elif prod!="" and insp_type!="" and op=="" and cname !="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,cname,insp_type,prod))
                elif prod!="" and insp_type!="" and op=="" and cname !="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,cname,insp_type,prod))
                elif prod!="" and insp_type!="" and op=="" and cname !="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,cname,insp_type,prod))

                elif prod!="" and insp_type!="" and op=="" and cname !="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,cname,insp_type,prod))
                elif prod!="" and insp_type!="" and op=="" and cname !="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,cname,insp_type,prod))
                elif prod!="" and insp_type!="" and op=="" and cname !="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,cname,insp_type,prod))
                elif prod!="" and insp_type!="" and op=="" and cname !="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,cname,insp_type,prod))

                elif prod!="" and insp_type!="" and op!="" and cname =="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s  AND INSPECTOR = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,op,insp_type,prod))
                elif prod!="" and insp_type!="" and op!="" and cname =="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,op,insp_type,prod))
                elif prod!="" and insp_type!="" and op!="" and cname =="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,op,insp_type,prod))
                elif prod!="" and insp_type!="" and op!="" and cname =="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,op,insp_type,prod))

                elif prod!="" and insp_type!="" and op!="" and cname =="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,op,insp_type,prod))
                elif prod!="" and insp_type!="" and op!="" and cname =="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,op,insp_type,prod))
                elif prod!="" and insp_type!="" and op!="" and cname =="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,op,insp_type,prod))
                elif prod!="" and insp_type!="" and op!="" and cname =="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,op,insp_type,prod))

                elif prod!="" and insp_type!="" and op!="" and cname !="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,cname,op,insp_type,prod))
                elif prod!="" and insp_type!="" and op!="" and cname !="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,cname,op,insp_type,prod))
                elif prod!="" and insp_type!="" and op!="" and cname !="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,cname,op,insp_type,prod))
                elif prod!="" and insp_type!="" and op!="" and cname !="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,cname,op,insp_type,prod))

                elif prod!="" and insp_type!="" and op!="" and cname !="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,cname,op,insp_type,prod))
                elif prod!="" and insp_type!="" and op!="" and cname !="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,cname,op,insp_type,prod))
                elif prod!="" and insp_type!="" and op!="" and cname !="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,cname,op,insp_type,prod))
                elif prod!="" and insp_type!="" and op!="" and cname !="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,cname,op,insp_type,prod))

                else:
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,cname,op,insp_type,prod))
                desc = cur.description
                column_names = [col[0] for col in desc]
                data = [dict(zip(column_names, row))for row in cur.fetchall()]
                conn.commit()
                conn.close()
                #print(data)
                return render_template('search.html', assetnumber=assetno, customername=customername, fromdate=fromdate, todate=todate, location=location, tbl=data, y=data, operator=op, select_1 = select_1,select_2 = select_2,select_3 = select_3,select_4 = select_4, inspectiontype=insp_type, producttype=prod)
                #return json.dumps({'success':True}), 200, {'ContentType':'application/json'}
            except Exception as e:
                #return json.dumps({'success':False}), 200, {'ContentType':'application/json'}
                print("Database connection failed due to {}".format(e))
                data=[]
                return render_template('search.html', assetnumber=assetno, customername=customername, fromdate=fromdate, todate=todate, location=location, tbl=data, y=data, operator=op, select_1 = select_1,select_2 = select_2,select_3 = select_3,select_4 = select_4, inspectiontype=insp_type, producttype=prod)

        elif "report" in request.form:
            try:
                b = datetime.strptime(b,'%Y-%m-%d').strftime('%Y-%m-%d')
                c = datetime.strptime(c,'%Y-%m-%d').strftime('%Y-%m-%d')
                ano = request.form['assetnumber']
                cname = request.form['customername']
                loc = request.form['location']
                op = request.form['operator']
                insp_type = request.form['inspectiontype']
                prod = producttype

                conn =  mysql.connector.connect(host=ENDPOINT, user=USR, passwd=token, port=PORT, database=DBNAME)
                cur = conn.cursor()

                if prod=="" and insp_type=="" and op=="" and cname =="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b))
                elif prod=="" and insp_type=="" and op=="" and cname =="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result))
                elif prod=="" and insp_type=="" and op=="" and cname =="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc))
                elif prod=="" and insp_type=="" and op=="" and cname =="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result))

                elif prod=="" and insp_type=="" and op=="" and cname =="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano))
                elif prod=="" and insp_type=="" and op=="" and cname =="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano))
                elif prod=="" and insp_type=="" and op=="" and cname =="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano))
                elif prod=="" and insp_type=="" and op=="" and cname =="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano))

                elif prod=="" and insp_type=="" and op=="" and cname !="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND CUSTOMER_NAME = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,cname))
                elif prod=="" and insp_type=="" and op=="" and cname !="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND CUSTOMER_NAME = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,cname))
                elif prod=="" and insp_type=="" and op=="" and cname !="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND CUSTOMER_NAME = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,cname))
                elif prod=="" and insp_type=="" and op=="" and cname !="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND CUSTOMER_NAME = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,cname))

                elif prod=="" and insp_type=="" and op=="" and cname !="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s AND CUSTOMER_NAME = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,cname))
                elif prod=="" and insp_type=="" and op=="" and cname !="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,cname))
                elif prod=="" and insp_type=="" and op=="" and cname !="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,cname))
                elif prod=="" and insp_type=="" and op=="" and cname !="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,cname))

                elif prod=="" and insp_type=="" and op!="" and cname =="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s  AND INSPECTOR = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,op))
                elif prod=="" and insp_type=="" and op!="" and cname =="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s  AND INSPECTOR = %s  ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,op))
                elif prod=="" and insp_type=="" and op!="" and cname =="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s  AND INSPECTOR = %s  ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,op))
                elif prod=="" and insp_type=="" and op!="" and cname =="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s  AND INSPECTOR = %s  ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,op))

                elif prod=="" and insp_type=="" and op!="" and cname =="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s  AND INSPECTOR = %s  ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,op))
                elif prod=="" and insp_type=="" and op!="" and cname =="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s  AND INSPECTOR = %s  ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,op))
                elif prod=="" and insp_type=="" and op!="" and cname =="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s  AND INSPECTOR = %s  ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,op))
                elif prod=="" and insp_type=="" and op!="" and cname =="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s  AND INSPECTOR = %s  ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,op))

                elif prod=="" and insp_type=="" and op!="" and cname !="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,cname,op))
                elif prod=="" and insp_type=="" and op!="" and cname !="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,cname,op))
                elif prod=="" and insp_type=="" and op!="" and cname !="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,cname,op))
                elif prod=="" and insp_type=="" and op!="" and cname !="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,cname,op))

                elif prod=="" and insp_type=="" and op!="" and cname !="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,cname,op))
                elif prod=="" and insp_type=="" and op!="" and cname !="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,cname,op))
                elif prod=="" and insp_type=="" and op!="" and cname !="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,cname,op))
                elif prod=="" and insp_type=="" and op!="" and cname !="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,cname,op))

                    ####################
                elif prod=="" and insp_type!="" and op=="" and cname =="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s  AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,insp_type))
                elif prod=="" and insp_type!="" and op=="" and cname =="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,insp_type))
                elif prod=="" and insp_type!="" and op=="" and cname =="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,insp_type))
                elif prod=="" and insp_type!="" and op=="" and cname =="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,insp_type))

                elif prod=="" and insp_type!="" and op=="" and cname =="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,insp_type))
                elif prod=="" and insp_type!="" and op=="" and cname =="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,insp_type))
                elif prod=="" and insp_type!="" and op=="" and cname =="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,insp_type))
                elif prod=="" and insp_type!="" and op=="" and cname =="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,insp_type))

                elif prod=="" and insp_type!="" and op=="" and cname !="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,cname,insp_type))
                elif prod=="" and insp_type!="" and op=="" and cname !="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,cname,insp_type))
                elif prod=="" and insp_type!="" and op=="" and cname !="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,cname,insp_type))
                elif prod=="" and insp_type!="" and op=="" and cname !="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,cname,insp_type))

                elif prod=="" and insp_type!="" and op=="" and cname !="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,cname,insp_type))
                elif prod=="" and insp_type!="" and op=="" and cname !="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,cname,insp_type))
                elif prod=="" and insp_type!="" and op=="" and cname !="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,cname,insp_type))
                elif prod=="" and insp_type!="" and op=="" and cname !="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,cname,insp_type))

                elif prod=="" and insp_type!="" and op!="" and cname =="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s  AND INSPECTOR = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,op,insp_type))
                elif prod=="" and insp_type!="" and op!="" and cname =="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,op,insp_type))
                elif prod=="" and insp_type!="" and op!="" and cname =="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,op,insp_type))
                elif prod=="" and insp_type!="" and op!="" and cname =="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,op,insp_type))

                elif prod=="" and insp_type!="" and op!="" and cname =="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,op,insp_type))
                elif prod=="" and insp_type!="" and op!="" and cname =="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,op,insp_type))
                elif prod=="" and insp_type!="" and op!="" and cname =="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,op,insp_type))
                elif prod=="" and insp_type!="" and op!="" and cname =="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,op,insp_type))

                elif prod=="" and insp_type!="" and op!="" and cname !="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,cname,op,insp_type))
                elif prod=="" and insp_type!="" and op!="" and cname !="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,cname,op,insp_type))
                elif prod=="" and insp_type!="" and op!="" and cname !="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,cname,op,insp_type))
                elif prod=="" and insp_type!="" and op!="" and cname !="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,cname,op,insp_type))

                elif prod=="" and insp_type!="" and op!="" and cname !="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,cname,op,insp_type))
                elif prod=="" and insp_type!="" and op!="" and cname !="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,cname,op,insp_type))
                elif prod=="" and insp_type!="" and op!="" and cname !="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,cname,op,insp_type))
                elif prod=="" and insp_type!="" and op!="" and cname !="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,cname,op,insp_type))

                ############################
                #######################################
                ####### PRODUCT NOT EMPTY

                elif prod!="" and insp_type=="" and op=="" and cname =="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s  AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,prod))
                elif prod!="" and insp_type=="" and op=="" and cname =="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,prod))
                elif prod!="" and insp_type=="" and op=="" and cname =="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,prod))
                elif prod!="" and insp_type=="" and op=="" and cname =="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,prod))

                elif prod!="" and insp_type=="" and op=="" and cname =="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,prod))
                elif prod!="" and insp_type=="" and op=="" and cname =="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,prod))
                elif prod!="" and insp_type=="" and op=="" and cname =="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,prod))
                elif prod!="" and insp_type=="" and op=="" and cname =="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,prod))

                elif prod!="" and insp_type=="" and op=="" and cname !="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND CUSTOMER_NAME = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,cname,prod))
                elif prod!="" and insp_type=="" and op=="" and cname !="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND CUSTOMER_NAME = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,cname,prod))
                elif prod!="" and insp_type=="" and op=="" and cname !="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND CUSTOMER_NAME = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,cname,prod))
                elif prod!="" and insp_type=="" and op=="" and cname !="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND CUSTOMER_NAME = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,cname,prod))

                elif prod!="" and insp_type=="" and op=="" and cname !="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,cname,prod))
                elif prod!="" and insp_type=="" and op=="" and cname !="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,cname,prod))
                elif prod!="" and insp_type=="" and op=="" and cname !="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,cname,prod))
                elif prod!="" and insp_type=="" and op=="" and cname !="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,cname,prod))

                elif prod!="" and insp_type=="" and op!="" and cname =="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s  AND INSPECTOR = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,op,prod))
                elif prod!="" and insp_type=="" and op!="" and cname =="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s  AND INSPECTOR = %s  AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,op,prod))
                elif prod!="" and insp_type=="" and op!="" and cname =="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s  AND INSPECTOR = %s  AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,op,prod))
                elif prod!="" and insp_type=="" and op!="" and cname =="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s  AND INSPECTOR = %s  AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,op,prod))

                elif prod!="" and insp_type=="" and op!="" and cname =="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s  AND INSPECTOR = %s  AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,op,prod))
                elif prod!="" and insp_type=="" and op!="" and cname =="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s  AND INSPECTOR = %s  AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,op,prod))
                elif prod!="" and insp_type=="" and op!="" and cname =="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s  AND INSPECTOR = %s  AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,op,prod))
                elif prod!="" and insp_type=="" and op!="" and cname =="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s  AND INSPECTOR = %s  AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,op,prod))

                elif prod!="" and insp_type=="" and op!="" and cname !="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,cname,op,prod))
                elif prod!="" and insp_type=="" and op!="" and cname !="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,cname,op,prod))
                elif prod!="" and insp_type=="" and op!="" and cname !="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,cname,op,prod))
                elif prod!="" and insp_type=="" and op!="" and cname !="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,cname,op,prod))

                elif prod!="" and insp_type=="" and op!="" and cname !="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,cname,op,prod))
                elif prod!="" and insp_type=="" and op!="" and cname !="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,cname,op,prod))
                elif prod!="" and insp_type=="" and op!="" and cname !="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,cname,op,prod))
                elif prod!="" and insp_type=="" and op!="" and cname !="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,cname,op,prod))

                    ####################
                elif prod!="" and insp_type!="" and op=="" and cname =="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s  AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,insp_type,prod))
                elif prod!="" and insp_type!="" and op=="" and cname =="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,insp_type,prod))
                elif prod!="" and insp_type!="" and op=="" and cname =="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,insp_type,prod))
                elif prod!="" and insp_type!="" and op=="" and cname =="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,insp_type,prod))

                elif prod!="" and insp_type!="" and op=="" and cname =="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,insp_type,prod))
                elif prod!="" and insp_type!="" and op=="" and cname =="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,insp_type,prod))
                elif prod!="" and insp_type!="" and op=="" and cname =="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,insp_type,prod))
                elif prod!="" and insp_type!="" and op=="" and cname =="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,insp_type,prod))

                elif prod!="" and insp_type!="" and op=="" and cname !="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,cname,insp_type,prod))
                elif prod!="" and insp_type!="" and op=="" and cname !="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,cname,insp_type,prod))
                elif prod!="" and insp_type!="" and op=="" and cname !="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,cname,insp_type,prod))
                elif prod!="" and insp_type!="" and op=="" and cname !="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,cname,insp_type,prod))

                elif prod!="" and insp_type!="" and op=="" and cname !="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,cname,insp_type,prod))
                elif prod!="" and insp_type!="" and op=="" and cname !="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,cname,insp_type,prod))
                elif prod!="" and insp_type!="" and op=="" and cname !="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,cname,insp_type,prod))
                elif prod!="" and insp_type!="" and op=="" and cname !="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,cname,insp_type,prod))

                elif prod!="" and insp_type!="" and op!="" and cname =="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s  AND INSPECTOR = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,op,insp_type,prod))
                elif prod!="" and insp_type!="" and op!="" and cname =="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,op,insp_type,prod))
                elif prod!="" and insp_type!="" and op!="" and cname =="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,op,insp_type,prod))
                elif prod!="" and insp_type!="" and op!="" and cname =="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,op,insp_type,prod))

                elif prod!="" and insp_type!="" and op!="" and cname =="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,op,insp_type,prod))
                elif prod!="" and insp_type!="" and op!="" and cname =="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,op,insp_type,prod))
                elif prod!="" and insp_type!="" and op!="" and cname =="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,op,insp_type,prod))
                elif prod!="" and insp_type!="" and op!="" and cname =="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,op,insp_type,prod))

                elif prod!="" and insp_type!="" and op!="" and cname !="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,cname,op,insp_type,prod))
                elif prod!="" and insp_type!="" and op!="" and cname !="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,cname,op,insp_type,prod))
                elif prod!="" and insp_type!="" and op!="" and cname !="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,cname,op,insp_type,prod))
                elif prod!="" and insp_type!="" and op!="" and cname !="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,cname,op,insp_type,prod))

                elif prod!="" and insp_type!="" and op!="" and cname !="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,cname,op,insp_type,prod))
                elif prod!="" and insp_type!="" and op!="" and cname !="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,cname,op,insp_type,prod))
                elif prod!="" and insp_type!="" and op!="" and cname !="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,cname,op,insp_type,prod))
                elif prod!="" and insp_type!="" and op!="" and cname !="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,cname,op,insp_type,prod))

                else:
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,cname,op,insp_type,prod))
                desc = cur.description
                column_names = [col[0] for col in desc]
                data = [dict(zip(column_names, row))for row in cur.fetchall()]
                conn.commit()
                conn.close()
            except:
                print("Database connection failed due to {}".format(e))
                data = []
                #return json.dumps({'success':False}), 200, {'ContentType':'application/json'}
                return render_template('search.html', assetnumber=assetno, customername=customername, fromdate=fromdate, todate=todate,tbl = results, location=location, producttype = producttype, inspectiontype=insp_type, result=result, y=data, operator=op, select_1 = select_1,select_2 = select_2,select_3 = select_3,select_4 = select_4)
            #@print(data)
            generate_report(data)
            return send_file("/Users/gunam/Desktop/flask/inspection.xlsx", as_attachment=True)

        elif "download" in request.form:
            try:
                b = datetime.strptime(b,'%Y-%m-%d').strftime('%Y-%m-%d')
                c = datetime.strptime(c,'%Y-%m-%d').strftime('%Y-%m-%d')
                ano = request.form['assetnumber']
                cname = request.form['customername']
                loc = request.form['location']
                op = request.form['operator']
                insp_type = request.form['inspectiontype']
                prod = producttype

                conn =  mysql.connector.connect(host=ENDPOINT, user=USR, passwd=token, port=PORT, database=DBNAME)
                cur = conn.cursor()

                if prod=="" and insp_type=="" and op=="" and cname =="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b))
                elif prod=="" and insp_type=="" and op=="" and cname =="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result))
                elif prod=="" and insp_type=="" and op=="" and cname =="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc))
                elif prod=="" and insp_type=="" and op=="" and cname =="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result))

                elif prod=="" and insp_type=="" and op=="" and cname =="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano))
                elif prod=="" and insp_type=="" and op=="" and cname =="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano))
                elif prod=="" and insp_type=="" and op=="" and cname =="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano))
                elif prod=="" and insp_type=="" and op=="" and cname =="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano))

                elif prod=="" and insp_type=="" and op=="" and cname !="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND CUSTOMER_NAME = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,cname))
                elif prod=="" and insp_type=="" and op=="" and cname !="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND CUSTOMER_NAME = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,cname))
                elif prod=="" and insp_type=="" and op=="" and cname !="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND CUSTOMER_NAME = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,cname))
                elif prod=="" and insp_type=="" and op=="" and cname !="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND CUSTOMER_NAME = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,cname))

                elif prod=="" and insp_type=="" and op=="" and cname !="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s AND CUSTOMER_NAME = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,cname))
                elif prod=="" and insp_type=="" and op=="" and cname !="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,cname))
                elif prod=="" and insp_type=="" and op=="" and cname !="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,cname))
                elif prod=="" and insp_type=="" and op=="" and cname !="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,cname))

                elif prod=="" and insp_type=="" and op!="" and cname =="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s  AND INSPECTOR = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,op))
                elif prod=="" and insp_type=="" and op!="" and cname =="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s  AND INSPECTOR = %s  ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,op))
                elif prod=="" and insp_type=="" and op!="" and cname =="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s  AND INSPECTOR = %s  ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,op))
                elif prod=="" and insp_type=="" and op!="" and cname =="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s  AND INSPECTOR = %s  ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,op))

                elif prod=="" and insp_type=="" and op!="" and cname =="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s  AND INSPECTOR = %s  ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,op))
                elif prod=="" and insp_type=="" and op!="" and cname =="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s  AND INSPECTOR = %s  ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,op))
                elif prod=="" and insp_type=="" and op!="" and cname =="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s  AND INSPECTOR = %s  ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,op))
                elif prod=="" and insp_type=="" and op!="" and cname =="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s  AND INSPECTOR = %s  ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,op))

                elif prod=="" and insp_type=="" and op!="" and cname !="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,cname,op))
                elif prod=="" and insp_type=="" and op!="" and cname !="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,cname,op))
                elif prod=="" and insp_type=="" and op!="" and cname !="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,cname,op))
                elif prod=="" and insp_type=="" and op!="" and cname !="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,cname,op))

                elif prod=="" and insp_type=="" and op!="" and cname !="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,cname,op))
                elif prod=="" and insp_type=="" and op!="" and cname !="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,cname,op))
                elif prod=="" and insp_type=="" and op!="" and cname !="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,cname,op))
                elif prod=="" and insp_type=="" and op!="" and cname !="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,cname,op))

                    ####################
                elif prod=="" and insp_type!="" and op=="" and cname =="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s  AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,insp_type))
                elif prod=="" and insp_type!="" and op=="" and cname =="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,insp_type))
                elif prod=="" and insp_type!="" and op=="" and cname =="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,insp_type))
                elif prod=="" and insp_type!="" and op=="" and cname =="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,insp_type))

                elif prod=="" and insp_type!="" and op=="" and cname =="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,insp_type))
                elif prod=="" and insp_type!="" and op=="" and cname =="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,insp_type))
                elif prod=="" and insp_type!="" and op=="" and cname =="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,insp_type))
                elif prod=="" and insp_type!="" and op=="" and cname =="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,insp_type))

                elif prod=="" and insp_type!="" and op=="" and cname !="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,cname,insp_type))
                elif prod=="" and insp_type!="" and op=="" and cname !="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,cname,insp_type))
                elif prod=="" and insp_type!="" and op=="" and cname !="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,cname,insp_type))
                elif prod=="" and insp_type!="" and op=="" and cname !="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,cname,insp_type))

                elif prod=="" and insp_type!="" and op=="" and cname !="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,cname,insp_type))
                elif prod=="" and insp_type!="" and op=="" and cname !="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,cname,insp_type))
                elif prod=="" and insp_type!="" and op=="" and cname !="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,cname,insp_type))
                elif prod=="" and insp_type!="" and op=="" and cname !="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,cname,insp_type))

                elif prod=="" and insp_type!="" and op!="" and cname =="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s  AND INSPECTOR = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,op,insp_type))
                elif prod=="" and insp_type!="" and op!="" and cname =="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,op,insp_type))
                elif prod=="" and insp_type!="" and op!="" and cname =="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,op,insp_type))
                elif prod=="" and insp_type!="" and op!="" and cname =="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,op,insp_type))

                elif prod=="" and insp_type!="" and op!="" and cname =="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,op,insp_type))
                elif prod=="" and insp_type!="" and op!="" and cname =="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,op,insp_type))
                elif prod=="" and insp_type!="" and op!="" and cname =="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,op,insp_type))
                elif prod=="" and insp_type!="" and op!="" and cname =="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,op,insp_type))

                elif prod=="" and insp_type!="" and op!="" and cname !="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,cname,op,insp_type))
                elif prod=="" and insp_type!="" and op!="" and cname !="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,cname,op,insp_type))
                elif prod=="" and insp_type!="" and op!="" and cname !="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,cname,op,insp_type))
                elif prod=="" and insp_type!="" and op!="" and cname !="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,cname,op,insp_type))

                elif prod=="" and insp_type!="" and op!="" and cname !="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,cname,op,insp_type))
                elif prod=="" and insp_type!="" and op!="" and cname !="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,cname,op,insp_type))
                elif prod=="" and insp_type!="" and op!="" and cname !="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,cname,op,insp_type))
                elif prod=="" and insp_type!="" and op!="" and cname !="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s AND INSPECTION_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,cname,op,insp_type))

                ############################
                #######################################
                ####### PRODUCT NOT EMPTY

                elif prod!="" and insp_type=="" and op=="" and cname =="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s  AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,prod))
                elif prod!="" and insp_type=="" and op=="" and cname =="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,prod))
                elif prod!="" and insp_type=="" and op=="" and cname =="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,prod))
                elif prod!="" and insp_type=="" and op=="" and cname =="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,prod))

                elif prod!="" and insp_type=="" and op=="" and cname =="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,prod))
                elif prod!="" and insp_type=="" and op=="" and cname =="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,prod))
                elif prod!="" and insp_type=="" and op=="" and cname =="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,prod))
                elif prod!="" and insp_type=="" and op=="" and cname =="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,prod))

                elif prod!="" and insp_type=="" and op=="" and cname !="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND CUSTOMER_NAME = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,cname,prod))
                elif prod!="" and insp_type=="" and op=="" and cname !="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND CUSTOMER_NAME = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,cname,prod))
                elif prod!="" and insp_type=="" and op=="" and cname !="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND CUSTOMER_NAME = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,cname,prod))
                elif prod!="" and insp_type=="" and op=="" and cname !="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND CUSTOMER_NAME = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,cname,prod))

                elif prod!="" and insp_type=="" and op=="" and cname !="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,cname,prod))
                elif prod!="" and insp_type=="" and op=="" and cname !="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,cname,prod))
                elif prod!="" and insp_type=="" and op=="" and cname !="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,cname,prod))
                elif prod!="" and insp_type=="" and op=="" and cname !="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,cname,prod))

                elif prod!="" and insp_type=="" and op!="" and cname =="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s  AND INSPECTOR = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,op,prod))
                elif prod!="" and insp_type=="" and op!="" and cname =="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s  AND INSPECTOR = %s  AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,op,prod))
                elif prod!="" and insp_type=="" and op!="" and cname =="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s  AND INSPECTOR = %s  AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,op,prod))
                elif prod!="" and insp_type=="" and op!="" and cname =="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s  AND INSPECTOR = %s  AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,op,prod))

                elif prod!="" and insp_type=="" and op!="" and cname =="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s  AND INSPECTOR = %s  AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,op,prod))
                elif prod!="" and insp_type=="" and op!="" and cname =="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s  AND INSPECTOR = %s  AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,op,prod))
                elif prod!="" and insp_type=="" and op!="" and cname =="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s  AND INSPECTOR = %s  AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,op,prod))
                elif prod!="" and insp_type=="" and op!="" and cname =="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s  AND INSPECTOR = %s  AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,op,prod))

                elif prod!="" and insp_type=="" and op!="" and cname !="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,cname,op,prod))
                elif prod!="" and insp_type=="" and op!="" and cname !="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,cname,op,prod))
                elif prod!="" and insp_type=="" and op!="" and cname !="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,cname,op,prod))
                elif prod!="" and insp_type=="" and op!="" and cname !="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,cname,op,prod))

                elif prod!="" and insp_type=="" and op!="" and cname !="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,cname,op,prod))
                elif prod!="" and insp_type=="" and op!="" and cname !="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,cname,op,prod))
                elif prod!="" and insp_type=="" and op!="" and cname !="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,cname,op,prod))
                elif prod!="" and insp_type=="" and op!="" and cname !="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,cname,op,prod))

                    ####################
                elif prod!="" and insp_type!="" and op=="" and cname =="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s  AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,insp_type,prod))
                elif prod!="" and insp_type!="" and op=="" and cname =="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,insp_type,prod))
                elif prod!="" and insp_type!="" and op=="" and cname =="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,insp_type,prod))
                elif prod!="" and insp_type!="" and op=="" and cname =="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,insp_type,prod))

                elif prod!="" and insp_type!="" and op=="" and cname =="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,insp_type,prod))
                elif prod!="" and insp_type!="" and op=="" and cname =="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,insp_type,prod))
                elif prod!="" and insp_type!="" and op=="" and cname =="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,insp_type,prod))
                elif prod!="" and insp_type!="" and op=="" and cname =="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,insp_type,prod))

                elif prod!="" and insp_type!="" and op=="" and cname !="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,cname,insp_type,prod))
                elif prod!="" and insp_type!="" and op=="" and cname !="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,cname,insp_type,prod))
                elif prod!="" and insp_type!="" and op=="" and cname !="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,cname,insp_type,prod))
                elif prod!="" and insp_type!="" and op=="" and cname !="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,cname,insp_type,prod))

                elif prod!="" and insp_type!="" and op=="" and cname !="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,cname,insp_type,prod))
                elif prod!="" and insp_type!="" and op=="" and cname !="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,cname,insp_type,prod))
                elif prod!="" and insp_type!="" and op=="" and cname !="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,cname,insp_type,prod))
                elif prod!="" and insp_type!="" and op=="" and cname !="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,cname,insp_type,prod))

                elif prod!="" and insp_type!="" and op!="" and cname =="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s  AND INSPECTOR = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,op,insp_type,prod))
                elif prod!="" and insp_type!="" and op!="" and cname =="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,op,insp_type,prod))
                elif prod!="" and insp_type!="" and op!="" and cname =="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,op,insp_type,prod))
                elif prod!="" and insp_type!="" and op!="" and cname =="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,op,insp_type,prod))

                elif prod!="" and insp_type!="" and op!="" and cname =="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,op,insp_type,prod))
                elif prod!="" and insp_type!="" and op!="" and cname =="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,op,insp_type,prod))
                elif prod!="" and insp_type!="" and op!="" and cname =="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,op,insp_type,prod))
                elif prod!="" and insp_type!="" and op!="" and cname =="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,op,insp_type,prod))

                elif prod!="" and insp_type!="" and op!="" and cname !="" and ano =="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,cname,op,insp_type,prod))
                elif prod!="" and insp_type!="" and op!="" and cname !="" and ano =="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result,cname,op,insp_type,prod))
                elif prod!="" and insp_type!="" and op!="" and cname !="" and ano =="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,cname,op,insp_type,prod))
                elif prod!="" and insp_type!="" and op!="" and cname !="" and ano =="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result,cname,op,insp_type,prod))

                elif prod!="" and insp_type!="" and op!="" and cname !="" and ano !="" and loc =="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,cname,op,insp_type,prod))
                elif prod!="" and insp_type!="" and op!="" and cname !="" and ano !="" and loc =="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,result, ano,cname,op,insp_type,prod))
                elif prod!="" and insp_type!="" and op!="" and cname !="" and ano !="" and loc !="" and result=="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,ano,cname,op,insp_type,prod))
                elif prod!="" and insp_type!="" and op!="" and cname !="" and ano !="" and loc !="" and result!="":
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,cname,op,insp_type,prod))

                else:
                    command = """SELECT * FROM INSPECTIONS WHERE INSPECTION_DATE <= %s AND INSPECTION_DATE >= %s AND LOCATION = %s AND RESULT = %s AND ASSETNO = %s AND CUSTOMER_NAME = %s  AND INSPECTOR = %s  AND INSPECTION_TYPE = %s AND PRODUCT_TYPE = %s ORDER BY STR_TO_DATE(INSPECTION_DATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,result, ano,cname,op,insp_type,prod))
                desc = cur.description
                column_names = [col[0] for col in desc]
                data = [dict(zip(column_names, row))for row in cur.fetchall()]
                conn.commit()
                conn.close()
            except:
                print("Database connection failed due to {}".format(e))
                data = []
                #return json.dumps({'success':False}), 200, {'ContentType':'application/json'}
                return render_template('search.html', assetnumber=assetno, customername=customername, fromdate=fromdate, todate=todate,tbl = results, location=location, producttype = producttype, inspectiontype=insp_type, result=result, y=data, operator=op, select_1 = select_1,select_2 = select_2,select_3 = select_3,select_4 = select_4)
            df = pd.DataFrame(data=data)
            df.to_csv("/Users/gunam/Desktop/flask/download.csv", sep=',',index=False)
            return send_file("/Users/gunam/Desktop/flask/download.csv", as_attachment=True)

        else:
            results=[]
            y = results
            return render_template('search.html',y=y)

    else:
        results=[]
        y = results
        return render_template('search.html',y=y)


@app.route('/pdfpdf/', methods=['GET','POST'])
def pdfpdf():
    print("hii")
    idd = request.args.get('id', default='', type=str)
    print(idd)
    #return redirect(idd)
    with open(idd, 'rb') as static_file:
        return send_file(static_file, attachment_filename="blank.pdf")




@app.route('/newform', methods=['GET','POST'])
def newform():
    if request.method =='POST':

        # user = current_user.get_id()
        # print(user)
        email = request.form['email']
        print(email)
        customername = request.form['customername']
        location = request.form['location']
        order = request.form['order']
        assetno = request.form['assetno']
        serialno = request.form['serial']
        asset = request.form['asset']
        product = request.form['producttype']
        operator = request.form['inspector']
        inspection = request.form['inspectiontype']
        date = request.form['inspectiondate']
        due_date = request.form['duedate']
        checklist = request.form['checklist']
        salesmen = request.form['salesmen']
        size = request.form['size']
        length = request.form['length']
        wll = request.form['wll']
        result = request.form['result']
        comment = request.form['comments']
        select_1 = ""
        select_2 =""
        select_3 =""
        select_4 =""
        select_5 =""
        select_6 =""
        select_1_1=""
        select_1_2=""
        select_1_3=""
        select_1_4=""
        select_1_5=""

        if result == "CHOOSE":
            select_1_1 = "selected"

        elif result == "PASS":
            select_1_2 = "selected"

        elif result == "FAIL":
            select_1_3 = "selected"

        elif result == "REPAIR":
            select_1_4 = "selected"

        else:
            select_1_5 = "selected"

        if "save" in request.form and checklist=='nothing':
            print("save")
            try:
                date = datetime.strptime(date,'%Y-%m-%d').strftime('%Y-%m-%d')
                date = str(date)
                due_date = datetime.strptime(due_date,'%Y-%m-%d').strftime('%Y-%m-%d')
                due_date = str(due_date)
                formid = str(uuid.uuid4()).replace('-','')
                #pdf_name = formid+".pdf"
                pdf_location = "/Reports/Muncy/No_Checklist/blank.pdf"
                conn =  mysql.connector.connect(host=ENDPOINT, user=USR, passwd=token, port=PORT, database=DBNAME)
                cur = conn.cursor()
                command = """INSERT INTO INSPECTIONS (FORMID , ASSETNO, CUSTOMER_NAME, LOCATION, ORDERNO, ASSET_DESCRIPTION,  PRODUCT_TYPE, INSPECTOR, INSPECTION_TYPE, INSPECTION_DATE, SALESMEN, SIZE, LENGTH, WLL, RESULT, COMMENTS, SERIALNO, CHECKLIST_NAME, DUE_DATE, PDF_LOCATION) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,%s,%s, %s)"""
                cur.execute(command,(formid, assetno, customername, location, order, asset, product, operator, inspection, date, salesmen, size, length, wll ,result, comment,serialno,checklist,due_date, pdf_location))
                conn.commit()
                conn.close()
                return json.dumps({'success':True}), 200, {'ContentType':'application/json'}
            except Exception as e:
                print("Database connection failed due to {}".format(e))
                return json.dumps({'success':False}), 200, {'ContentType':'application/json'}

        elif "save" in request.form and checklist=='forklift':
            print("forklift")
            try:
                date = datetime.strptime(date,'%Y-%m-%d').strftime('%Y-%m-%d')
                date = str(date)
                due_date = datetime.strptime(due_date,'%Y-%m-%d').strftime('%Y-%m-%d')
                due_date = str(due_date)
                formid = str(uuid.uuid4()).replace('-','')
                link_formid = str(uuid.uuid4()).replace('-','')
                ######### FORKLIFT DATA
                fork_formid = str(uuid.uuid4()).replace('-','')
                forkliftid = request.form["assetno"]
                fork_date = date
                fork_inspector = request.form["inspector"]
                fork_notes = request.form["notes"]
                notes = fork_notes
                forks = request.form["forks"]
                pdf_name = formid+"_forklift.pdf"
                pdf_location = "/Reports/Muncy/Forklift/"+pdf_name
                if forks == "True":
                    forks = True
                else:
                    forks = False
                mast = request.form["mast"]
                if mast == "True":
                    mast = True
                else:
                    mast = False
                tires = request.form["tires"]
                if tires == "True":
                    tires= True
                else:
                    tires = False
                overhead = request.form["overhead"]
                if overhead == "True":
                    overhead = True
                else:
                    foverhead = False
                fuel_tank = request.form["fuel_tank"]
                if fuel_tank == "True":
                    fuel_tank = True
                else:
                    fuel_tank = False
                engine_oil = request.form["engine_oil"]
                if engine_oil == "True":
                    engine_oil = True
                else:
                    engine_oil = False
                water_level = request.form["water_level"]
                if water_level == "True":
                    water_level = True
                else:
                    water_level = False
                fuel_level = request.form["fuel_level"]
                if fuel_level == "True":
                    fuel_level = True
                else:
                    fuel_level = False
                leaks = request.form["leaks"]
                if leaks == "True":
                    leaks = True
                else:
                    leaks = False
                seat_belt = request.form["seat_belt"]
                if seat_belt == "True":
                    seat_belt = True
                else:
                    seat_belt = False
                horn = request.form["horn"]
                if horn == "True":
                    horn = True
                else:
                    horn = False
                lights = request.form["lights"]
                if lights  == "True":
                    lights = True
                else:
                    lights  = False
                gauges_instruments = request.form["gauges_instruments"]
                if gauges_instruments == "True":
                    gauges_instruments = True
                else:
                    gauges_instruments = False
                all_brakes = request.form["all_brakes"]
                if all_brakes == "True":
                    all_brakes = True
                else:
                    all_brakes = False

                hydraulic = request.form["hydraulic"]
                if hydraulic == "True":
                    hydraulic = True
                else:
                    hydraulic = False

                steering = request.form["steering"]
                if steering == "True":
                    steering = True
                else:
                    steering = False

                brake_fluid = request.form["brake_fluid"]
                if brake_fluid == "True":
                    brake_fluid = True
                else:
                    brake_fluid = False

                radiator = request.form["radiator"]
                if radiator == "True":
                    radiator = True
                else:
                    radiator = False
                nameplate = request.form["nameplate"]
                if nameplate == "True":
                    nameplate = True
                else:
                    nameplate = False

                electrolyte = request.form["eletrolyte"]
                if electrolyte == "True":
                    electrolyte = True
                else:
                    electrolyte = False

                forklift1(pdf_name,operator,serialno,date,fork_notes,result,forks,mast,tires,overhead,fuel_tank,engine_oil,water_level,fuel_level,leaks,seat_belt,horn,lights,gauges_instruments,all_brakes,hydraulic,steering,brake_fluid,radiator,nameplate,electrolyte)
                #forklift(pdf_name,operator,serialno,date,fork_notes,result,forks,mast,tires,overhead,fuel_tank,engine_oil,water_level,fuel_level,leaks,seat_belt,horn,lights,gauges_instruments,all_brakes,hydraulic,steering,brake_fluid,radiator,nameplate,electrolyte)
                conn =  mysql.connector.connect(host=ENDPOINT, user=USR, passwd=token, port=PORT, database=DBNAME)
                cur = conn.cursor()
                command = """INSERT INTO INSPECTION_FORKLIFT (FORMID, ASSETNO, INSPECTION_DATE, INSPECTOR, FORKS, BACKREST, CARRIAGE, MAST, CHAINS, HYDRAULIC_LINES, TIRES, AXLES, OVERHEAD_GUARD, FUELTANK_CONNECTIONS, ENGINE_OIL_LEVEL, WATER_LEVEL, FUEL_LEVEL, LEAKS, SEAT_BELT, HORN, BACKUP_ALARAM, LIGHTS, GAUGES_INSTRUMENTS, ALL_BRAKES, HYDRAULIC_CONTROLS_LIFT, STEERING, NAMPLATE, BRAKE_FLUID, RADIATOR_WATER_LEVEL, ELECTROLYTE, INSPECTION_NOTES) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
                cur.execute(command,(fork_formid, forkliftid, fork_date, fork_inspector, forks, forks, forks, mast, mast, mast, tires, tires, overhead, fuel_tank, engine_oil, water_level, fuel_level, leaks, seat_belt, horn, horn, lights, gauges_instruments, all_brakes, hydraulic, steering, nameplate, brake_fluid, radiator, electrolyte, notes ))
                conn.commit()
                command = """INSERT INTO INSPECTION_FORMS (FORMID, INSPECTION_FORKLIFT_ID) VALUES (%s, %s)"""
                cur.execute(command,(link_formid,fork_formid))
                conn.commit()
                command = """INSERT INTO INSPECTIONS (FORMID , ASSETNO, CUSTOMER_NAME, LOCATION, ORDERNO, ASSET_DESCRIPTION,  PRODUCT_TYPE, INSPECTOR, INSPECTION_TYPE, INSPECTION_DATE, SALESMEN, SIZE, LENGTH, WLL, RESULT, COMMENTS, INSPECTION_FORMS_ID, SERIALNO, CHECKLIST_NAME, DUE_DATE, PDF_NAME, PDF_LOCATION) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
                cur.execute(command,(formid, assetno, customername, location, order, asset, product, operator, inspection, date, salesmen, size, length, wll ,result, comment, link_formid, serialno, checklist, due_date, pdf_name, pdf_location))
                conn.commit()
                conn.close()
                return json.dumps({'success':True}), 200, {'ContentType':'application/json'}
            except Exception as e:
                print("Database connection failed due to {}".format(e))
                return json.dumps({'success':False}), 200, {'ContentType':'application/json'}

        elif "save" in request.form and checklist=='calipers':
            print("calipers")
            try:
                date = datetime.strptime(date,'%Y-%m-%d').strftime('%Y-%m-%d')
                date = str(date)
                due_date = datetime.strptime(due_date,'%Y-%m-%d').strftime('%Y-%m-%d')
                due_date = str(due_date)
                formid = str(uuid.uuid4()).replace('-','')
                pdf_name = formid+"_caliper.pdf"
                pdf_location = "/Reports/Muncy/Calipers/"+pdf_name

                link_formid = str(uuid.uuid4()).replace('-','')
                ######### CALIPERS DATA
                cal_formid = str(uuid.uuid4()).replace('-','')
                calid = request.form["assetno"]
                caldate = date
                caldesc = request.form["asset"]
                calsize = request.form["size"]
                calduedate = request.form["due_date"]
                std1_idno = request.form["stand1_id"]
                std1_dd = request.form["stand1"]
                std1_dd = datetime.strptime(std1_dd,'%Y-%m-%d').strftime('%Y-%m-%d')
                std2_idno = request.form["stand2_id"]
                std2_dd = request.form["stand2"]
                std3_idno = request.form["stand3_id"]
                std3_dd = request.form["stand3"]
                std4_idno = request.form["stand4_id"]
                std4_dd = request.form["stand4"]
                std5_idno = request.form["stand5_id"]
                std5_dd = request.form["stand5"]
                std6_idno = request.form["stand6_id"]
                std6_dd = request.form["stand6"]
                notes = request.form["notes_calib"]
                calibrator = request.form["calibrator_by"]
                calresult = request.form["result_calib"]
                std2_dd = datetime.strptime(std2_dd,'%Y-%m-%d').strftime('%Y-%m-%d')
                std3_dd = datetime.strptime(std3_dd,'%Y-%m-%d').strftime('%Y-%m-%d')
                std4_dd = datetime.strptime(std4_dd,'%Y-%m-%d').strftime('%Y-%m-%d')
                std5_dd = datetime.strptime(std5_dd,'%Y-%m-%d').strftime('%Y-%m-%d')
                std6_dd = datetime.strptime(std6_dd,'%Y-%m-%d').strftime('%Y-%m-%d')

                damage = request.form["damage"]
                if damage == "true":
                    damage = True
                else:
                    damage = False

                nicks = request.form["nicks"]
                if nicks == "true":
                    nicks = True
                else:
                    nicks = False

                burrs = request.form["burrs"]
                if burrs == "true":
                    burrs = True
                else:
                    burrs = False

                parallel = request.form["parallel"]
                if parallel == "true":
                    parallel = True
                else:
                    parallel = False

                ######### OUTSIDE JAWS
                out_m1 = request.form["out_m1"]
                out_t1 = request.form["out_t1"]
                out_a1 = request.form["out_a1"]
                out_m2 = request.form["out_m2"]
                out_t2 = request.form["out_t2"]
                out_a2 = request.form["out_a2"]
                out_m3 = request.form["out_m3"]
                out_t3 = request.form["out_t3"]
                out_a3 = request.form["out_a3"]
                out_m4 = request.form["out_m4"]
                out_t4 = request.form["out_t4"]
                out_a4 = request.form["out_a4"]
                out_m5 = request.form["out_m5"]
                out_t5 = request.form["out_t5"]
                out_a5 = request.form["out_a5"]

                ######### INSIDE JAWS
                in_m1 = request.form["in_m1"]
                in_t1 = request.form["in_t1"]
                in_a1 = request.form["in_a1"]
                in_m2 = request.form["in_m2"]
                in_t2 = request.form["in_t2"]
                in_a2 = request.form["in_a2"]
                in_m3 = request.form["in_m3"]
                in_t3 = request.form["in_t3"]
                in_a3 = request.form["in_a3"]
                in_m4 = request.form["in_m4"]
                in_t4 = request.form["in_t4"]
                in_a4 = request.form["in_a4"]
                in_m5 = request.form["in_m5"]
                in_t5 = request.form["in_t5"]
                in_a5 = request.form["in_a5"]

                ######### DEPTH JAWS
                depth_m1 = request.form["depth_m1"]
                depth_t1 = request.form["depth_t1"]
                depth_a1 = request.form["depth_a1"]
                depth_m2 = request.form["depth_m2"]
                depth_t2 = request.form["depth_t2"]
                depth_a2 = request.form["depth_a2"]
                depth_m3 = request.form["depth_m3"]
                depth_t3 = request.form["depth_t3"]
                depth_a3 = request.form["depth_a3"]
                depth_m4 = request.form["depth_m4"]
                depth_t4 = request.form["depth_t4"]
                depth_a4 = request.form["depth_a4"]
                depth_m5 = request.form["depth_m5"]
                depth_t5 = request.form["depth_t5"]
                depth_a5 = request.form["depth_a5"]

                pdf_gen(pdf_name,operator,asset,size,assetno,serialno,calduedate,caldate, std1_idno,std2_idno,std3_idno,std4_idno,std5_idno,std6_idno,std1_dd,std2_dd,std3_dd,std4_dd,std5_dd,std6_dd,out_m1,out_m2,out_m3,out_m4,out_m5,out_a1,out_a2,out_a3,out_a4,out_a5,in_m1,in_m2,in_m3,in_m4,in_m5,in_a1,in_a2,in_a3,in_a4,in_a5,depth_m1,depth_m2,depth_m3,depth_m4,depth_m5,depth_a1,depth_a2,depth_a3,depth_a4,depth_a5,notes,calresult)

                conn =  mysql.connector.connect(host=ENDPOINT, user=USR, passwd=token, port=PORT, database=DBNAME)
                cur = conn.cursor()
                command = """INSERT INTO INSPECTION_CALIPERS (FORMID,ASSETNO,INSTRUMENT_DESCRIPTION,INSTRUMENT_SIZE,CALIBRATION_DUEDATE,DATE_OF_CALIBRATION,STANDARD1_IDNO,STANDARD1_CDATE,STANDARD2_IDNO,STANDARD2_CDATE ,STANDARD3_IDNO,STANDARD3_CDATE ,STANDARD4_IDNO,STANDARD4_CDATE,STANDARD5_IDNO,STANDARD5_CDATE,STANDARD6_IDNO,STANDARD6_CDATE,NOTES ,CALIBRATOR ,RESULT,DAMAGE,NICKS,BURNS,STRAIGHT_PARALLEL,OUTSIDEJAWS_ACTLENGTH1,OUTSIDEJAWS_MESLENGTH1,OUTSIDEJAWS_TOLERANCE1,OUTSIDEJAWS_ACTLENGTH2,OUTSIDEJAWS_MESLENGTH2,OUTSIDEJAWS_TOLERANCE2,OUTSIDEJAWS_ACTLENGTH3,OUTSIDEJAWS_MESLENGTH3,OUTSIDEJAWS_TOLERANCE3,OUTSIDEJAWS_ACTLENGTH4,OUTSIDEJAWS_MESLENGTH4,OUTSIDEJAWS_TOLERANCE4,OUTSIDEJAWS_ACTLENGTH5,OUTSIDEJAWS_MESLENGTH5 ,OUTSIDEJAWS_TOLERANCE5,INSIDEJAWS_ACTLENGTH1 ,INSIDEJAWS_MESLENGTH1,INSIDEJAWS_TOLERANCE1 ,INSIDEJAWS_ACTLENGTH2,INSIDEJAWS_MESLENGTH2,INSIDEJAWS_TOLERANCE2,INSIDEJAWS_ACTLENGTH3,INSIDEJAWS_MESLENGTH3,INSIDEJAWS_TOLERANCE3,INSIDEJAWS_ACTLENGTH4,INSIDEJAWS_MESLENGTH4,INSIDEJAWS_TOLERANCE4,INSIDEJAWS_ACTLENGTH5,INSIDEJAWS_MESLENGTH5,INSIDEJAWS_TOLERANCE5,DEPTHGAUGE_ACTLENGTH1,DEPTHGAUGE_MESLENGTH1,DEPTHGAUGE_TOLERANCE1,DEPTHGAUGE_ACTLENGTH2,DEPTHGAUGE_MESLENGTH2,DEPTHGAUGE_TOLERANCE2,DEPTHGAUGE_ACTLENGTH3,DEPTHGAUGE_MESLENGTH3,DEPTHGAUGE_TOLERANCE3,DEPTHGAUGE_ACTLENGTH4,DEPTHGAUGE_MESLENGTH4,DEPTHGAUGE_TOLERANCE4,DEPTHGAUGE_ACTLENGTH5,DEPTHGAUGE_MESLENGTH5,DEPTHGAUGE_TOLERANCE5 ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
                cur.execute(command,(cal_formid, calid, caldesc, calsize, calduedate, caldate,std1_idno,std1_dd,std2_idno,std2_dd,std3_idno,std3_dd,std4_idno,std4_dd,std5_idno,std5_dd,std6_idno,std6_dd,notes, calibrator, calresult, damage, nicks, burrs, parallel,out_m1,out_t1,out_a1 ,out_m2,out_t2,out_a2 ,out_m3,out_t3,out_a3 ,out_m4,out_t4,out_a4 ,out_m5,out_t5,out_a5,in_m1,in_t1,in_a1, in_m2,in_t2,in_a2, in_m3,in_t3,in_a3, in_m4,in_t4,in_a4, in_m5,in_t5,in_a5, depth_m1,depth_t1,depth_a1, depth_m2,depth_t2,depth_a2, depth_m3,depth_t3,depth_a3, depth_m4,depth_t4,depth_a4, depth_m5,depth_t5,depth_a5   ))
                conn.commit()
                command = """INSERT INTO INSPECTION_FORMS (FORMID, INSPECTION_CALIPERS_ID) VALUES (%s, %s)"""
                cur.execute(command,(link_formid,cal_formid))
                conn.commit()
                command = """INSERT INTO INSPECTIONS (FORMID , ASSETNO, CUSTOMER_NAME, LOCATION, ORDERNO, ASSET_DESCRIPTION,  PRODUCT_TYPE, INSPECTOR, INSPECTION_TYPE, INSPECTION_DATE, SALESMEN, SIZE, LENGTH, WLL, RESULT, COMMENTS, INSPECTION_FORMS_ID, SERIALNO, CHECKLIST_NAME, DUE_DATE, PDF_NAME, PDF_LOCATION) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
                cur.execute(command,(formid, assetno, customername, location, order, asset, product, operator, inspection, date, salesmen, size, length, wll ,result, comment, link_formid, serialno, checklist, due_date, pdf_name, pdf_location))
                conn.commit()
                conn.close()
                return json.dumps({'success':True}), 200, {'ContentType':'application/json'}
            except Exception as e:
                print("Database connection failed due to {}".format(e))
                return json.dumps({'success':False}), 200, {'ContentType':'application/json'}

        elif "save" in request.form and checklist=='fire':
            print("fire_protection")
            try:
                date = datetime.strptime(date,'%Y-%m-%d').strftime('%Y-%m-%d')
                date = str(date)
                formid = str(uuid.uuid4()).replace('-','')
                link_formid = str(uuid.uuid4()).replace('-','')
                pdf_name = formid+"_fire_protection.pdf"
                pdf_location = "/Reports/Muncy/Fire_Protection/"+pdf_name
                ################# FIRE PROTECTION
                fire_formid = str(uuid.uuid4()).replace('-','')
                fire_id = request.form["assetno"]
                fire_date = date
                address = request.form["address"]
                model = request.form["model"]
                city_st_zip = request.form["city"]
                area = request.form["area"]
                choose_system = request.form["choose_system"]
                system_type = request.form["system_type"]
                inspection_notes = request.form["inspection_notes"]
                technician = request.form["technician"]
                calib_date = request.form["calib_date"]
                agent = request.form["agent"]

                phoneno = request.form["phoneno"]
                owner = request.form["owner"]
                type_service = request.form["type_service"]
                locsystem = request.form["locsystem"]
                ######## CHECKBOXES

                q1 = request.form["q1"]
                q2 = request.form["q2"]
                q3 = request.form["q3"]
                q4 = request.form["q4"]
                q5 = request.form["q5"]
                q6 = request.form["q6"]
                q7 = request.form["q7"]
                q8 = request.form["q8"]

                q9_test_date = request.form["testdate"]
                q9 = request.form["q9"]
                q10 = request.form["q10"]
                q11 = request.form["q11"]
                q12 = request.form["q12"]

                q13_deg_135 = request.form["deg_135"]
                q13_deg_165 = request.form["deg_165"]
                q13_deg_212 = request.form["deg_212"]
                q13_deg_280 = request.form["deg_280"]
                q13_deg_360 = request.form["deg_360"]
                q13_deg_450 = request.form["deg_450"]
                q13_deg_500 = request.form["deg_500"]
                q13_deg_other = request.form["deg_other"]

                q14_deg_225 = request.form["deg_225"]
                q14_deg_325 = request.form["deg_325"]
                q14_deg_450 = request.form["deg_450"]
                q14_deg_600 = request.form["deg_600"]

                q15 = request.form["q15"]
                q16 = request.form["q16"]
                q16_mfg_date = request.form["mfg_date"]
                q17_done_on = request.form["done_on"]

                q18 = request.form["q18"]
                q19 = request.form["q19"]
                q20 = request.form["q20"]
                q21 = request.form["q21"]
                q22 = request.form["q22"]
                q23 = request.form["q23"]
                q24 = request.form["q24"]
                q25 = request.form["q25"]
                q26 = request.form["q26"]
                q27 = request.form["q27"]
                q28 = request.form["q28"]
                q29 = request.form["q29"]
                q30 = request.form["q30"]
                q31 = request.form["q31"]
                q32 = request.form["q32"]
                q33 = request.form["q33"]
                q34 = request.form["q34"]
                q35 = request.form["q35"]

                fire_protection(pdf_name,operator,customername, address, city_st_zip, area, calib_date, agent, model, system_type, inspection_notes, result, choose_system, q1, q2, q3, q4, q5, q6, q7, q8, q9, q9_test_date, q10, q11, q12, q13_deg_135, q13_deg_165, q13_deg_212, q13_deg_280, q13_deg_360, q13_deg_450, q13_deg_500, q13_deg_other, q14_deg_225, q14_deg_325, q14_deg_450, q14_deg_600, q15, q16, q16_mfg_date, q17_done_on,q18,q19,q20,q21,q22,q23,q24,q25,q26,q27,q28,q29,q30,q31,q32,q33,q34,q35,phoneno,owner,type_service,locsystem)
                conn =  mysql.connector.connect(host=ENDPOINT, user=USR, passwd=token, port=PORT, database=DBNAME)
                cur = conn.cursor()
                command = """ INSERT INTO INSPECTION_FIRE_PROTECTION (FORMID,ASSETNO,ADDRESS,MODEL,CITY_ST_ZIP,AREA_PROTECTED,CHOOSE_SYSTEM,SYSTEM_TYPE,CALIBRATION_DATE,Q1,Q2,Q3,Q4,Q5,Q6,Q7,Q8,Q9,Q9_TEST_DATE,Q10,Q11,Q12,Q13_DEG_135,Q13_DEG_165,Q13_DEG_212,Q13_DEG_280,Q13_DEG_360,Q13_DEG_450,Q13_DEG_500,Q13_DEG_OTHER,Q14_DEG_225,Q14_DEG_325 ,Q14_DEG_450,Q14_DEG_600,Q15,Q16,Q16_MFG_DATE,Q17_DONE_ON,Q18,Q19,Q20,Q21,Q22,Q23,Q24,Q25,Q26,Q27,Q28,Q29,Q30,Q31,Q32,Q33,Q34,Q35,INSPECTION_NOTES,TECHNICIAN,AGENT) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) """
                cur.execute(command,(fire_formid,fire_id,address,model,city_st_zip,area,choose_system,system_type,calib_date,q1,q2,q3,q4,q5,q6,q7,q8,q9,q9_test_date,q10,q11,q12,q13_deg_135,q13_deg_165,q13_deg_212,q13_deg_280,q13_deg_360,q13_deg_450,q13_deg_500,q13_deg_other,q14_deg_225,q14_deg_325,q14_deg_450,q14_deg_600,q15,q16,q16_mfg_date,q17_done_on,q18,q19,q20,q21,q22,q23,q24,q25,q26,q27,q28,q29,q30,q31,q32,q33,q34,q35,inspection_notes,technician,agent))
                conn.commit()
                command = """INSERT INTO INSPECTION_FORMS (FORMID, INSPECTION_FIRE_ID) VALUES (%s, %s)"""
                cur.execute(command,(link_formid,fire_formid))
                conn.commit()
                command = """INSERT INTO INSPECTIONS (FORMID , ASSETNO, CUSTOMER_NAME, LOCATION, ORDERNO, ASSET_DESCRIPTION,  PRODUCT_TYPE, INSPECTOR, INSPECTION_TYPE, INSPECTION_DATE, SALESMEN, SIZE, LENGTH, WLL, RESULT, COMMENTS, INSPECTION_FORMS_ID, SERIALNO, CHECKLIST_NAME, DUE_DATE, PDF_NAME, PDF_LOCATION) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
                cur.execute(command,(formid, assetno, customername, location, order, asset, product, operator, inspection, date, salesmen, size, length, wll ,result, comment, link_formid, serialno, checklist, due_date, pdf_name, pdf_location))
                conn.commit()
                conn.close()
                return json.dumps({'success':True}), 200, {'ContentType':'application/json'}
            except Exception as e:
                print("Database connection failed due to {}".format(e))
                return json.dumps({'success':False}), 200, {'ContentType':'application/json'}

        elif "save" in request.form and checklist=='micro':
            try:
                date = datetime.strptime(date,'%Y-%m-%d').strftime('%Y-%m-%d')
                date = str(date)
                due_date = datetime.strptime(due_date,'%Y-%m-%d').strftime('%Y-%m-%d')
                due_date = str(due_date)
                formid = str(uuid.uuid4()).replace('-','')
                pdf_name = formid+"_micro.pdf"
                pdf_location = "/Reports/Muncy/Micrometer"+pdf_name
                link_formid = str(uuid.uuid4()).replace('-','')
                ######### MICROMETER DATA
                micro_formid = str(uuid.uuid4()).replace('-','')
                micro_id = request.form["assetno"]
                calib_by = request.form["calib_by"]
                calib_due_date = request.form["due_date"]
                date_of_calib = request.form["date_of_calib"]
                calib_result = request.form["calib_result"]
                calib_notes = request.form["calib_notes"]

                std1_idno = request.form["stand1_id"]
                std1_dd = request.form["stand1"]
                std2_idno = request.form["stand2_id"]
                std2_dd = request.form["stand2"]
                std3_idno = request.form["stand3_id"]
                std3_dd = request.form["stand3"]
                std4_idno = request.form["stand4_id"]
                std4_dd = request.form["stand4"]
                std5_idno = request.form["stand5_id"]
                std5_dd = request.form["stand5"]
                std6_idno = request.form["stand6_id"]
                std6_dd = request.form["stand6"]

                ####### OUTSIDE
                out_clean = request.form["out_clean"]
                out_test_method = request.form["out_test_method"]
                out_ratchet = request.form["out_ratchet"]
                out_damage = request.form["out_damage"]
                out_nicks = request.form["out_nicks"]
                out_burrs = request.form["out_burrs"]
                out_parallel = request.form["out_parallel"]

                out_m1 = request.form["out_m1"]
                out_t1 = request.form["out_t1"]
                out_a1 = request.form["out_a1"]
                out_m2 = request.form["out_m2"]
                out_t2 = request.form["out_t2"]
                out_a2 = request.form["out_a2"]
                out_m3 = request.form["out_m3"]
                out_t3 = request.form["out_t3"]
                out_a3 = request.form["out_a3"]
                out_m4 = request.form["out_m4"]
                out_t4 = request.form["out_t4"]
                out_a4 = request.form["out_a4"]
                out_m5 = request.form["out_m5"]
                out_t5 = request.form["out_t5"]
                out_a5 = request.form["out_a5"]

                out_rod_m1 = request.form["out_rod_m1"]
                out_rod_t1 = request.form["out_rod_t1"]
                out_rod_a1 = request.form["out_rod_a1"]
                out_rod_m2 = request.form["out_rod_m2"]
                out_rod_t2 = request.form["out_rod_t2"]
                out_rod_a2 = request.form["out_rod_a2"]
                out_rod_m3 = request.form["out_rod_m3"]
                out_rod_t3 = request.form["out_rod_t3"]
                out_rod_a3 = request.form["out_rod_a3"]
                out_rod_m4 = request.form["out_rod_m4"]
                out_rod_t4 = request.form["out_rod_t4"]
                out_rod_a4 = request.form["out_rod_a4"]
                out_rod_m5 = request.form["out_rod_m5"]
                out_rod_t5 = request.form["out_rod_t5"]
                out_rod_a5 = request.form["out_rod_a5"]

                ####### INSIDE
                in_clean = request.form["in_clean"]
                in_test_method = request.form["in_test_method"]
                in_ratchet = request.form["in_ratchet"]
                in_damage = request.form["in_damage"]
                in_nicks = request.form["in_nicks"]
                in_burrs = request.form["in_burrs"]
                in_parallel = request.form["in_parallel"]

                in_m1 = request.form["in_m1"]
                in_t1 = request.form["in_t1"]
                in_a1 = request.form["in_a1"]
                in_m2 = request.form["in_m2"]
                in_t2 = request.form["in_t2"]
                in_a2 = request.form["in_a2"]
                in_m3 = request.form["in_m3"]
                in_t3 = request.form["in_t3"]
                in_a3 = request.form["in_a3"]
                in_m4 = request.form["in_m4"]
                in_t4 = request.form["in_t4"]
                in_a4 = request.form["in_a4"]
                in_m5 = request.form["in_m5"]
                in_t5 = request.form["in_t5"]
                in_a5 = request.form["in_a5"]

                in_rod_m1 = request.form["in_rod_m1"]
                in_rod_t1 = request.form["in_rod_t1"]
                in_rod_a1 = request.form["in_rod_a1"]
                in_rod_m2 = request.form["in_rod_m2"]
                in_rod_t2 = request.form["in_rod_t2"]
                in_rod_a2 = request.form["in_rod_a2"]
                in_rod_m3 = request.form["in_rod_m3"]
                in_rod_t3 = request.form["in_rod_t3"]
                in_rod_a3 = request.form["in_rod_a3"]
                in_rod_m4 = request.form["in_rod_m4"]
                in_rod_t4 = request.form["in_rod_t4"]
                in_rod_a4 = request.form["in_rod_a4"]
                in_rod_m5 = request.form["in_rod_m5"]
                in_rod_t5 = request.form["in_rod_t5"]
                in_rod_a5 = request.form["in_rod_a5"]

                ####### DEPTH
                depth_clean = request.form["depth_clean"]
                depth_test_method = request.form["depth_test_method"]
                depth_ratchet = request.form["depth_ratchet"]
                depth_damage = request.form["depth_damage"]
                depth_nicks = request.form["depth_nicks"]
                depth_burrs = request.form["depth_burrs"]
                depth_parallel = request.form["depth_parallel"]

                depth_m1 = request.form["depth_m1"]
                depth_t1 = request.form["depth_t1"]
                depth_a1 = request.form["depth_a1"]
                depth_m2 = request.form["depth_m2"]
                depth_t2 = request.form["depth_t2"]
                depth_a2 = request.form["depth_a2"]
                depth_m3 = request.form["depth_m3"]
                depth_t3 = request.form["depth_t3"]
                depth_a3 = request.form["depth_a3"]
                depth_m4 = request.form["depth_m4"]
                depth_t4 = request.form["depth_t4"]
                depth_a4 = request.form["depth_a4"]
                depth_m5 = request.form["depth_m5"]
                depth_t5 = request.form["depth_t5"]
                depth_a5 = request.form["depth_a5"]

                depth_rod_m1 = request.form["depth_rod_m1"]
                depth_rod_t1 = request.form["depth_rod_t1"]
                depth_rod_a1 = request.form["depth_rod_a1"]
                depth_rod_m2 = request.form["depth_rod_m2"]
                depth_rod_t2 = request.form["depth_rod_t2"]
                depth_rod_a2 = request.form["depth_rod_a2"]
                depth_rod_m3 = request.form["depth_rod_m3"]
                depth_rod_t3 = request.form["depth_rod_t3"]
                depth_rod_a3 = request.form["depth_rod_a3"]
                depth_rod_m4 = request.form["depth_rod_m4"]
                depth_rod_t4 = request.form["depth_rod_t4"]
                depth_rod_a4 = request.form["depth_rod_a4"]
                depth_rod_m5 = request.form["depth_rod_m5"]
                depth_rod_t5 = request.form["depth_rod_t5"]
                depth_rod_a5 = request.form["depth_rod_a5"]

                if out_a1 == "" and in_a1 == "":
                    depth_micrometer(pdf_name,operator,asset,size,micro_id,serialno,calib_due_date,date_of_calib,std1_idno,std2_idno,std3_idno,std4_idno,std5_idno,std6_idno,std1_dd,std2_dd,std3_dd,std4_dd,std5_dd,std6_dd,depth_m1,depth_m2,depth_m3,depth_m4,depth_m5,depth_t1,depth_t2,depth_t3,depth_t4,depth_t5,depth_a1,depth_a2,depth_a3,depth_a4,depth_a5,depth_rod_m1,depth_rod_m2,depth_rod_m3,depth_rod_m4,depth_rod_m5,depth_rod_t1,depth_rod_t2,depth_rod_t3,depth_rod_t4,depth_rod_t5,depth_rod_a1,depth_rod_a2,depth_rod_a3,depth_rod_a4,depth_rod_a5,calib_notes,calib_result)
                if depth_a1 == "" and out_a1=="":
                    inside_micrometer(pdf_name,operator,asset,size,micro_id,serialno,calib_due_date,date_of_calib,std1_idno,std2_idno,std3_idno,std4_idno,std5_idno,std6_idno,std1_dd,std2_dd,std3_dd,std4_dd,std5_dd,std6_dd,in_m1,in_m2,in_m3,in_m4,in_m5,in_t1,in_t2,in_t3,in_t4,in_t5,in_a1,in_a2,in_a3,in_a4,in_a5,in_rod_m1,in_rod_m2,in_rod_m3,in_rod_m4,in_rod_m5,in_rod_a1,in_rod_a2,in_rod_a3,in_rod_a4,in_rod_a5,in_rod_t1,in_rod_t2,in_rod_t3,in_rod_t4,in_rod_t5,calib_notes,calib_result)
                if depth_a1 == "" and in_a1 == "":
                    outside_micrometer(pdf_name,operator,asset,size,micro_id,serialno,calib_due_date,date_of_calib,std1_idno,std2_idno,std3_idno,std4_idno,std5_idno,std6_idno,std1_dd,std2_dd,std3_dd,std4_dd,std5_dd,std6_dd,out_m1,out_m2,out_m3,out_m4,out_m5,out_t1,out_t2,out_t3,out_t4,out_t5,out_a1,out_a2,out_a3,out_a4,out_a5,out_rod_m1,out_rod_m2,out_rod_m3,out_rod_m4,out_rod_m5,out_rod_a1,out_rod_a2,out_rod_a3,out_rod_a4,out_rod_a5,out_rod_t1,out_rod_t2,out_rod_t3,out_rod_t4,out_rod_t5,calib_notes,calib_result)
                conn =  mysql.connector.connect(host=ENDPOINT, user=USR, passwd=token, port=PORT, database=DBNAME)
                cur = conn.cursor()
                command = """ INSERT INTO INSPECTION_MICROMETER (FORMID,ASSETNO,CALIBRATED_BY,DUE_DATE,DATE_OF_CALIBRATION,CALIBRATION_RESULT,CALIBRATION_NOTES,STANDARD1_IDNO,STANDARD1_CDATE,STANDARD2_IDNO,STANDARD2_CDATE,STANDARD3_IDNO,STANDARD3_CDATE,STANDARD4_IDNO,STANDARD4_CDATE,STANDARD5_IDNO,STANDARD5_CDATE,STANDARD6_IDNO,STANDARD6_CDATE,OUT_CLEAN,OUT_TEST_METHOD,OUT_RATCHET,OUT_DAMAGE,OUT_NICKS,OUT_BURRS,OUT_PARALLEL,OUT_ACTLENGTH1,OUT_MESLENGTH1,OUT_TOLERANCE1,OUT_ACTLENGTH2,OUT_MESLENGTH2,OUT_TOLERANCE2,OUT_ACTLENGTH3,OUT_MESLENGTH3,OUT_TOLERANCE3,OUT_ACTLENGTH4,OUT_MESLENGTH4,OUT_TOLERANCE4,OUT_ACTLENGTH5,OUT_MESLENGTH5,OUT_TOLERANCE5,OUT_ROD_ACTLENGTH1,OUT_ROD_MESLENGTH1,OUT_ROD_TOLERANCE1,OUT_ROD_ACTLENGTH2,OUT_ROD_MESLENGTH2,OUT_ROD_TOLERANCE2,OUT_ROD_ACTLENGTH3,OUT_ROD_MESLENGTH3,OUT_ROD_TOLERANCE3,OUT_ROD_ACTLENGTH4,OUT_ROD_MESLENGTH4,OUT_ROD_TOLERANCE4,OUT_ROD_ACTLENGTH5,OUT_ROD_MESLENGTH5,OUT_ROD_TOLERANCE5,IN_CLEAN,IN_TEST_METHOD,IN_RATCHET,IN_DAMAGE,IN_NICKS,IN_BURRS,IN_PARALLEL,IN_ACTLENGTH1,IN_MESLENGTH1,IN_TOLERANCE1,IN_ACTLENGTH2,IN_MESLENGTH2,IN_TOLERANCE2,IN_ACTLENGTH3,IN_MESLENGTH3,IN_TOLERANCE3,IN_ACTLENGTH4,IN_MESLENGTH4,IN_TOLERANCE4,IN_ACTLENGTH5,IN_MESLENGTH5,IN_TOLERANCE5,IN_ROD_ACTLENGTH1,IN_ROD_MESLENGTH1,IN_ROD_TOLERANCE1,IN_ROD_ACTLENGTH2,IN_ROD_MESLENGTH2,IN_ROD_TOLERANCE2,IN_ROD_ACTLENGTH3,IN_ROD_MESLENGTH3,IN_ROD_TOLERANCE3,IN_ROD_ACTLENGTH4,IN_ROD_MESLENGTH4,IN_ROD_TOLERANCE4,IN_ROD_ACTLENGTH5,IN_ROD_MESLENGTH5,IN_ROD_TOLERANCE5,DEPTH_CLEAN,DEPTH_TEST_METHOD,DEPTH_RATCHET,DEPTH_DAMAGE,DEPTH_NICKS,DEPTH_BURRS,DEPTH_PARALLEL,DEPTH_ACTLENGTH1,DEPTH_MESLENGTH1,DEPTH_TOLERANCE1,DEPTH_ACTLENGTH2,DEPTH_MESLENGTH2,DEPTH_TOLERANCE2,DEPTH_ACTLENGTH3,DEPTH_MESLENGTH3,DEPTH_TOLERANCE3,DEPTH_ACTLENGTH4,DEPTH_MESLENGTH4,DEPTH_TOLERANCE4,DEPTH_ACTLENGTH5,DEPTH_MESLENGTH5,DEPTH_TOLERANCE5,DEPTH_ROD_ACTLENGTH1,DEPTH_ROD_MESLENGTH1,DEPTH_ROD_TOLERANCE1,DEPTH_ROD_ACTLENGTH2,DEPTH_ROD_MESLENGTH2,DEPTH_ROD_TOLERANCE2,DEPTH_ROD_ACTLENGTH3,DEPTH_ROD_MESLENGTH3,DEPTH_ROD_TOLERANCE3,DEPTH_ROD_ACTLENGTH4,DEPTH_ROD_MESLENGTH4,DEPTH_ROD_TOLERANCE4,DEPTH_ROD_ACTLENGTH5,DEPTH_ROD_MESLENGTH5,DEPTH_ROD_TOLERANCE5) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) """
                cur.execute(command,(micro_formid,micro_id,calib_by,calib_due_date,date_of_calib,calib_result,calib_notes,std1_idno,std1_dd,std2_idno,std2_dd,std3_idno,std3_dd,std4_idno,std4_dd,std5_idno,std5_dd,std6_idno,std6_dd,out_clean,out_test_method,out_ratchet,out_damage,out_nicks,out_burrs,out_parallel,out_a1,out_m1,out_t1,out_a2,out_m2,out_t2,out_a3,out_m3,out_t3,out_a4,out_m4,out_t4,out_a5,out_m5,out_t5,out_rod_a1,out_rod_m1,out_rod_t1,out_rod_a2,out_rod_m2,out_rod_t2,out_rod_a3,out_rod_m3,out_rod_t3,out_rod_a4,out_rod_m4,out_rod_t4,out_rod_a5,out_rod_m5,out_rod_t5,in_clean,in_test_method,in_ratchet,in_damage,in_nicks,in_burrs,in_parallel,in_a1,in_m1,in_t1,in_a2,in_m2,in_t2,in_a3,in_m3,in_t3,in_a4,in_m4,in_t4,in_a5,in_m5,in_t5,in_rod_a1,in_rod_m1,in_rod_t1,in_rod_a2,in_rod_m2,in_rod_t2,in_rod_a3,in_rod_m3,in_rod_t3,in_rod_a4,in_rod_m4,in_rod_t4,in_rod_a5,in_rod_m5,in_rod_t5,depth_clean,depth_test_method,depth_ratchet,depth_damage,depth_nicks,depth_burrs,depth_parallel,depth_a1,depth_m1,depth_t1,depth_a2,depth_m2,depth_t2,depth_a3,depth_m3,depth_t3,depth_a4,depth_m4,depth_t4,depth_a5,depth_m5,depth_t5,depth_rod_a1,depth_rod_m1,depth_rod_t1,depth_rod_a2,depth_rod_m2,depth_rod_t2,depth_rod_a3,depth_rod_m3,depth_rod_t3,depth_rod_a4,depth_rod_m4,depth_rod_t4,depth_rod_a5,depth_rod_m5,depth_rod_t5))
                conn.commit()
                command = """INSERT INTO INSPECTION_FORMS (FORMID, INSPECTION_MICROMETER_ID) VALUES (%s, %s)"""
                cur.execute(command,(link_formid,micro_formid))
                conn.commit()
                command = """INSERT INTO INSPECTIONS (FORMID , ASSETNO, CUSTOMER_NAME, LOCATION, ORDERNO, ASSET_DESCRIPTION,  PRODUCT_TYPE, INSPECTOR, INSPECTION_TYPE, INSPECTION_DATE, SALESMEN, SIZE, LENGTH, WLL, RESULT, COMMENTS, INSPECTION_FORMS_ID, SERIALNO, CHECKLIST_NAME, DUE_DATE, PDF_NAME, PDF_LOCATION) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
                cur.execute(command,(formid, assetno, customername, location, order, asset, product, operator, inspection, date, salesmen, size, length, wll ,result, comment, link_formid, serialno, checklist, due_date, pdf_name, pdf_location))
                conn.commit()
                conn.close()
                return json.dumps({'success':True}), 200, {'ContentType':'application/json'}
            except Exception as e:
                print("Database connection failed due to {}".format(e))
                return json.dumps({'success':False}), 200, {'ContentType':'application/json'}

        elif "save" in request.form and checklist=='crane':
            date = datetime.strptime(date,'%Y-%m-%d').strftime('%Y-%m-%d')
            date = str(date)
            formid = str(uuid.uuid4()).replace('-','')
            link_formid = str(uuid.uuid4()).replace('-','')

            ############### CRANE
            crane_formid = str(uuid.uuid4()).replace('-','')
            crane_asset = request.form["assetno"]
            address = request.form["address"]
            city = request.form["city"]
            submittername = request.form["submittername"]
            submissiondate = request.form["submissiondate"]
            serverdate = request.form["serverdate"]
            referencenumber = request.form["referencenumber"]
            customername1 =request.form["customername1"]
            capacity = request.form["capacity"]
            system_type = request.form["system_type"]
            power = request.form["power"]
            inspector = request.form["inspectors"]
            unitnumber = request.form["unitnumber"]
            inspect_date = request.form["inspect_date"]
            location = request.form["location"]
            hoistmanufacturer = request.form["hoistmanufacturer"]
            hoistserialnumber = request.form["hoistserialnumber"]
            modelnumber = request.form["modelnumber"]
            approximateheight = request.form["approximateheight"]
            basicinformationphoto = request.form["basicinformationphoto"]
            approximatespan = request.form["approximatespan"]
            capacitymarkings = request.form["capacitymarkings"]
            informationcomments = request.form["informationcomments"]
            maincontractortest = request.form["maincontractortest"]
            bridgetest = request.form["bridgetest"]
            testtrolleys = request.form["testtrolleys"]
            testhoists = request.form["testhoists"]
            testphoto = request.form["testphoto"]
            testcomments = request.form["testcomments"]
            pushbutton = request.form["pushbutton"]
            warninglabel = request.form["warninglabel"]
            functionlabels = request.form["functionlabels"]
            labelcomments = request.form["labelcomments"]
            festooncomments = request.form["festooncomments"]
            generalcondition = request.form["generalcondition"]
            festoontrack = request.form["festoontrack"]
            cableconnections = request.form["cableconnections"]
            pushbuttonphoto = request.form["pushbuttonphoto"]
            pushbuttonstrainrelief = request.form["pushbuttonstrainrelief"]
            pushbuttoncomments = request.form["pushbuttoncomments"]
            lowerhookcondition = request.form["lowerhookcondition"]
            lowerhooktrams = request.form["lowerhooktrams"]
            lowerhookthroat = request.form["lowerhookthroat"]
            lowerhooksaddle = request.form["lowerhooksaddle"]
            lowerhooksphoto = request.form["lowerhooksphoto"]
            lowerhookcomments = request.form["lowerhookcomments"]
            wireropecondition = request.form["wireropecondition"]
            wireropedia = request.form["wireropedia"]
            numberofparts = request.form["numberofparts"]
            wireropelubrication = request.form["wireropelubrication"]
            wireropephoto = request.form["wireropephoto"]
            wireropechainlinks = request.form["wireropechainlinks"]
            wireropecomments = request.form["wireropecomments"]
            lowersafetylatch = request.form["lowersafetylatch"]
            lowersheaves = request.form["lowersheaves"]
            lowerkeeperplates = request.form["lowerkeeperplates"]
            lowerthrustbearing = request.form["lowerthrustbearing"]
            lowerbolts = request.form["lowerbolts"]
            lowersheavesbearings = request.form["lowersheavesbearings"]
            lowersheaveguards = request.form["lowersheaveguards"]
            lowerblocksphoto = request.form["lowerblocksphoto"]
            lowerblockscomments = request.form["lowerblockscomments"]
            cabvisibility = request.form["cabvisibility"]
            cabclearance = request.form["cabclearance"]
            cabdriversseat = request.form["cabdriversseat"]
            cabdoor = request.form["cabdoor"]
            cabhousekeeping = request.form["cabhousekeeping"]
            cabsupports = request.form["cabsupports"]
            cabfanheater = request.form["cabfanheater"]
            cabphoto = request.form["cabphoto"]
            cabsafetylight = request.form["cabsafetylight"]
            cabfireextinguisher = request.form["cabfireextinguisher"]
            cabladder = request.form["cabladder"]
            cabsafetyphoto = request.form["cabsafetyphoto"]
            cabsafetycomments = request.form["cabsafetycomments"]
            cabcomments = request.form["cabcomments"]
            cabmastercontrollers = request.form["cabmastercontrollers"]
            cabfunctionlabels = request.form["cabfunctionlabels"]
            cabmainswitches = request.form["cabmainlineswitches"]
            cabgeneralwiring = request.form["cabgeneralwiring"]
            cabelectricphoto = request.form["cabelectricphoto"]
            cablighting = request.form["cablighting"]
            cabelectriccomments = request.form["cabeelectriccomments"]
            bridgeflooring = request.form["bridgeflooring"]
            bridgehandrails = request.form["bridgehandrails"]
            bridgetoeplate = request.form["bridgetoeplate"]
            bridgeheadroom = request.form["bridgeheadroom"]
            bridgewalkwayphoto = request.form["bridgewalkwayphoto"]
            bridgeopenings = request.form["bridgeopenings"]
            bridgeconditiongeneral = request.form["bridgeconditiongeneral"]
            bridgewalkwaycomments = request.form["bridgewalkwaycomments"]
            girderconnections = request.form["girderconnections"]
            bridgealignment = request.form["bridgealignment"]
            bridgerailclips = request.form["bridgerailclips"]
            bridgegeneralwelds = request.form["bridgegeneralwelds"]
            bridgecamber = request.form["bridgecamber"]
            bridgetopplate = request.form["bridgetopplate"]
            bridgeloadflanges = request.form["bridgeloadflanges"]
            structurephoto = request.form["structurephoto"]
            structurecomments = request.form["structurecomments"]
            endtruckconnections = request.form["endtruckconnections"]
            endtrucksafetylugs = request.form["endtrucksafetylugs"]
            endtruckbumpers = request.form["endtruckbumpers"]
            endtrucksweeperplates = request.form["endtrucksweeperplates"]
            endtruckphoto = request.form["endtruckphoto"]
            endtruckwheels = request.form["endtruckwheels"]
            endtruckbearings = request.form["endtruckbearings"]
            endtruckcomments = request.form["endtruckcomments"]
            driveoilseal = request.form["driveoilseal"]
            drivegearbox = request.form["drivegearbox"]
            drivegears = request.form["drivegears"]
            drivekeyways = request.form["drivekeyways"]
            driveseals = request.form["driveseals"]
            drivesupports = request.form["drivesupports"]
            drivebearing = request.form["drivebearing"]
            drivepinions = request.form["drivepinions"]
            bridgedrivephoto = request.form["bridgedrivephoto"]
            drivebolts = request.form["drivebolts"]
            drivebrakes = request.form["drivebrakes"]
            bridgedrivecomments = request.form["bridgedrivecomments"]
            bridgemotors = request.form["bridgemotors"]
            bridgesliprings = request.form["bridgesliprings"]
            bridgecommutor = request.form["bridgecommutor"]
            bridgebrushes = request.form["bridgebrushes"]
            bridgecovers = request.form["bridgecovers"]
            bridgemotorbearings = request.form["bridgemotorbearings"]
            bridgedisconnect = request.form["bridgedisconnect"]
            bridgehornbell = request.form["bridgehornbell"]
            bridgehorncomments = request.form["bridgecomments"]
            bridgegeneralconduits = request.form["bridgegeneralconduits"]
            bridgecontrolenclosure = request.form["bridgecontrolenclosure"]
            bridgecontroloperations = request.form["bridgecontroloperations"]
            bridgeresistors = request.form["bridgeresistors"]
            bridgetrolleyconductor = request.form["bridgetrolleyconductor"]
            bridgeconductor = request.form["bridgeconductor"]
            bridgeconductorcomments = request.form["bridgeconductorcomments"]
            bridgedisconnectphoto = request.form["bridgedisconnectphoto"]
            bridgeinsulators = request.form["bridgeinsulators"]
            bridgecollectorpoles = request.form["bridgecollectorpoles"]
            bridgeelectriccomments = request.form["bridgeelectriccomments"]
            trolleyconnections = request.form["trolleyconnections"]
            trolleyhoistconnections = request.form["trolleyhoistconnections"]
            trolleygeneralwelds = request.form["trolleygeneralwelds"]
            trolleysupports = request.form["trolleysupports"]
            trolleybumpers = request.form["trolleybumpers"]
            trolleybumpercomments = request.form["trolleybumpercomments"]
            trolleywheels = request.form["trolleywheels"]
            trolleywheelgears = request.form["trolleywheelgears"]
            trolleyphoto = request.form["trolleyphoto"]
            trolleyseallubrication = request.form["trolleyseallubrication"]
            trolleycapacitymarkings = request.form["trolleycapacitymarkings"]
            trolleystructurecomments = request.form["trolleystructurecomments"]
            trolleydisconnect = request.form["trolleydisconnect"]
            trolleymotors = request.form["trolleymotors"]
            trolleysliprings = request.form["trolleysliprings"]
            trolleycommutator = request.form["trolleycommutator"]
            trolleyholders = request.form["trolleyholders"]
            trolleymotorbearing = request.form["trolleymotorbearing"]
            trolleywiringandconduits = request.form["trolleywiringandconduits"]
            trolleycontrolenclosure = request.form["trolleycontrolenclosure"]
            trolleyelectricphoto = request.form["trolleyelectricphoto"]
            trolleycontroloperations = request.form["trolleycontroloperations"]
            trolleyresistors = request.form["trolleyresistors"]
            trolleyelectriccomments = request.form["trolleyelectriccomments"]
            tractorphoto = request.form["tractorphoto"]
            tractorwheelgauge = request.form["tractorwheelgauge"]
            tractorbumpers = request.form["tractorbumpers"]
            tractorcomments = request.form["tractorcomments"]
            hoistlimitswitch = request.form["hoistlimitswitch"]
            hoistmotors = request.form["hoistmotors"]
            hoistmotorbrake = request.form["hoistmotorbrake"]
            hoistloadbrake = request.form["hoistloadbrake"]
            hoistgearbox = request.form["hoistgearbox"]
            hoistupperblock = request.form["hoistupperblock"]
            hoistlowerblock = request.form["hoistlowerblock"]
            hoistsafetylatch = request.form["hoistsafetylatch"]
            hoisthooks = request.form["hoisthooks"]
            hoisthooktrams = request.form["hoisthooktrams"]
            hoistthroattrams = request.form["hoisthookthroat"]
            hoisthooksaddle = request.form["hoisthooksaddle"]
            hoistwireropeloadchain = request.form["hoistwireropeloadchain"]
            hoistropechain = request.form["hoistropechain"]
            hoistropedrum = request.form["hoistropedrum"]
            hoistchainlinks = request.form["hoistchainlinks"]
            hoistchaincontainer = request.form["hoistchaincontainer"]
            hoistholdingbrakes = request.form["hoistholdingbrake"]
            hoistmechanicaloperations = request.form["hoistmechanicaloperations"]
            hoistmechanicalinternal = request.form["hoistmechanicalinternal"]
            hoistvisual = request.form["hoistvisual"]
            hoistgearcase = request.form["hoistgearcase"]
            hoistbearings = request.form["hoistbearings"]
            hoistseals = request.form["hoistseals"]
            hoistsupports = request.form["hoistsupports"]
            hoistgears = request.form["hoistgears"]
            hoistpinions = request.form["hoistpinions"]
            hoistkeyways = request.form["hoistkeyways"]
            hoistcuplings = request.form["hoistcuplings"]
            hoistuppersheave = request.form["hoistuppersheave"]
            hoistlubrication = request.form["hoistlubrication"]
            hoistbolts = request.form["hoistbolts"]
            hoistphoto = request.form["hoistphoto"]
            hoistcomments = request.form["hoistcomments"]
            electrichoist = request.form["electrichoist"]
            electricmotors = request.form["electricmotors"]
            electricsliprings = request.form["electricsliprings"]
            electriccommutator = request.form["electriccommutator"]
            electricbrushes = request.form["electricbrushes"]
            electricenclosures = request.form["electricenclosures"]
            electricoperations = request.form["electricoperations"]
            electricresistors = request.form["electricresistors"]
            electricswitches = request.form["electricswitches"]
            electricloadlimit = request.form["electricloadlimit"]
            electricwiring = request.form["electricwiring"]
            electricwiringcomments = request.form["electricwiringcomments"]
            electricphoto = request.form["electricphoto"]
            hoistelectriccomments = request.form["hoistelectriccomments"]
            bridgeendtrucks = request.form["bridgeendtrucks"]
            bridgewheels = request.form["bridgewheels"]
            bridgegirders = request.form["bridgegirders"]
            bridgeendstops = request.form["bridgeendstops"]
            bridgephoto = request.form["bridgephoto"]
            bridgecomments = request.form["bridgecomments"]
            pendantcontrols = request.form["pendantcontrols"]
            directionallabels = request.form["directionallabels"]
            cablecontrols = request.form["cablecontrols"]
            strainreliefcable = request.form["strainreliefcable"]
            hoistcontrols = request.form["hoistcontrols"]
            resistorcontrols = request.form["resistorscontrols"]
            festooncontrols = request.form["festooncontrols"]
            controlsphoto = request.form["controlsphoto"]
            controlscomments = request.form["controlscomments"]
            monorailrailjoints = request.form["monorailrailjoints"]
            monorailendstops = request.form["monorailendstops"]
            monorailpowerfeed = request.form["monorailpowerfeed"]
            monorailcapacity = request.form["monorailcapacity"]
            monorailphoto = request.form["monorailphoto"]
            monorailcomments = request.form["monorailcomments"]
            runwayrails = request.form["runwayrails"]
            runwaysupportbeam = request.form["runwaysupportbeam"]
            runwaysupportplates = request.form["runwaysupportplates"]
            runwayendstops = request.form["runwayendstops"]
            runwayphoto = request.form["runwayphoto"]
            runwayrailwear = request.form["runwayrailwear"]
            runwaycomments = request.form["runwaycomments"]
            craneabove = request.form["craneabove"]
            cranesides = request.form["cranesides"]
            craneloadtest = request.form["craneloadtest"]
            cranecomments = request.form["cranecomments"]
            cranephoto = request.form["cranephoto"]
            cranedisconnect = request.form["cranedisconnect"]
            craneextracomments = request.form["craneextracomments"]

            conn =  mysql.connector.connect(host=ENDPOINT, user=USR, passwd=token, port=PORT, database=DBNAME)
            cur = conn.cursor()
            command = """INSERT INTO INSPECTION_CRANE (FORMID,ASSETNO, ADDRESS, CITY, SUBMITTER_NAME, SUBMISSION_DATE, SERVER_DATE, REFERENCE_NUMBER,CUSTOMER_NAME, CAPACITY, SYSTEM_TYPE, POWER, INSPECTOR, UNIT_NUMBER, INSPECT_DATE, LOCATION, HOIST_MANUFACTURER, HOIST_SERIAL_NUMBER, MODEL_NUMBER, APPROXIMATE_HEIGHT, BASIC_INFORMATION_PHOTO, APPROXIMATE_SPAN, CAPACITY_MARKINGS, INFORMATION_COMMENTS, MAIN_CONTRACTOR_TEST, BRIDGE_TEST, TEST_TROLLEYS, TEST_HOISTS, TEST_PHOTO, TEST_COMMENTS,PUSH_BUTTON, WARNING_LABEL, FUNCTION_LABELS, LABEL_COMMENTS, FESTOON_COMMENTS, GENERAL_CONDITION, FESTOON_TRACK, CABLE_CONNECTIONS, PUSH_BUTTON_PHOTO, PUSH_BUTTON_STRAIN_RELIEF, PUSH_BUTTON_COMMENTS, LOWER_HOOK_CONDITION, LOWER_HOOK_TRAMS, LOWER_HOOK_THROAT, LOWER_HOOK_SADDLE, LOWER_HOOKS_PHOTO, LOWER_HOOK_COMMENTS, WIRE_ROPE_CONDITION, WIRE_ROPE_DIA, NUMBER_OF_PARTS,WIRE_ROPE_LUBRICATION, WIRE_ROPE_PHOTO, WIRE_ROPE_CHAIN_LINKS, WIRE_ROPE_COMMENTS,LOWER_SAFETY_LATCH, LOWER_SHEAVES, LOWER_KEEPER_PLATES, LOWER_THRUST_BEARING, LOWER_BOLTS, LOWER_SHEAVES_BEARINGS, LOWER_SHEAVE_GUARDS, LOWER_BLOCKS_PHOTO, LOWER_BLOCKS_COMMENTS, CAB_VISIBILITY, CAB_CLEARANCE, CAB_DRIVERS_SEAT, CAB_DOOR, CAB_HOUSE_KEEPING, CAB_SUPPORTS, CAB_FAN_HEATER, CAB_PHOTO, CAB_COMMENTS, CAB_SAFETY_LIGHT,CAB_FIRE_EXTINGUISHER, CAB_LADDER, CAB_SAFETY_PHOTO, CAB_SAFETY_COMMENTS, CAB_MASTER_CONTROLLERS,CAB_FUNCTION_LABELS,CAB_MAIN_SWITCHES,CAB_GENERAL_WIRING, CAB_ELECTRIC_PHOTO, CAB_LIGHTING, CAB_ELECTRIC_COMMENTS, BRIDGE_FLOORING, BRIDGE_HAND_RAILS, BRIDGE_TOE_PLATES, BRIDGE_HEAD_ROOM, BRIDGE_WALK_WAY_PHOTO, BRIDGE_OPENINGS, BRIDGE_CONDITIONAL_GENERAL, BRIDGE_WALK_WAY_COMMENTS, GIRDER_CONNECTIONS, BRIDGE_ALIGNMENT, BRIDGE_RAIL_CLIPS, BRIDGE_GENERAL_WELDS, BRIDGE_CAMBER, BRIDGE_TOP_PLATE, BRIDGE_LOAD_FLANGES, STRUCTURE_PHOTO, STRUCTURE_COMMENTS, END_TRUCK_CONNECTIONS, END_TRUCK_SAFETY_LUGS,END_TRUCK_BUMPERS, END_TRUCK_SWEEPER_PLATES, END_TRUCK_PHOTO, END_TRUCK_WHEELS, END_TRUCK_BEARINGS, END_TRUCK_COMMENTS, DRIVE_OIL_SEAL, DRIVE_GEAR_BOX, DRIVE_GEARS, DRIVE_KEY_WAYS, DRIVE_SEALS, DRIVE_SUPPORTS, DRIVE_BEARING, DRIVE_PINIONS, BRIDGE_DRIVE_PHOTO, DRIVE_BOLTS, DRIVE_BRAKES, BRIDGE_DRIVE_COMMENTS, BRIDGE_MOTORS, BRIDGE_SLIP_RINGS, BRIDGE_COMMUTOR, BRIDGE_BRUSHES,BRIDGE_COVERS, BRIDGE_MOTOR_BEARINGS, BRIDGE_DISCONNECT,BRIDGE_HORN_BELL,BRIDGE_HORN_COMMENTS, BRIDGE_GENERAL_CONDUITS, BRIDGE_CONTROL_ENCLOSURE,BRIDGE_CONTROL_OPERATIONS, BRIDGE_RESISTORS, BRIDGE_TROLLEY_CONDUCTOR, BRIDGE_CONDUCTOR, BRIDGE_CONDUCTOR_COMMENTS, BRIDGE_DISCONNECT_PHOTO, BRIDGE_INSULATORS,BRIDGE_COLLECTOR_POLES, BRIDGE_ELECTRIC_COMMENTS, TROLLEY_CONNECTIONS, TROLLEY_HOIST_CONNECTIONS,TROLLEY_GENERAL_WELDS, TROLLEY_SUPPORTS, TROLLEY_BUMPERS,TROLLEY_BUMPER_COMMENTS, TROLLEY_WHEELS, TROLLEY_WHEEL_GEARS,TROLLEY_PHOTO, TROLLEY_SEAL_LUBRICATION, TROLLEY_CAPACITY_MARKINGS, TROLLEY_STRUCTURE_COMMENTS, TROLLEY_DISCONNECT,TROLLEY_MOTORS, TROLLEY_SLIP_RINGS, TROLLEY_COMMUTATOR,TROLLEY_HOLDERS,TROLLEY_MOTOR_BEARING,TROLLEY_WIRING_AND_CONDUITS, TROLLEY_CONTROL_ENCLOSURE, TROLLEY_ELECTRIC_PHOTO, TROLLEY_CONTROL_OPERATIONS, TROLLEY_RESISTORS, TROLLEY_ELECTRIC_COMMENTS, TRACKTER_PHOTO, TRACTOR_WHEEL_GAUGE, TRACTOR_BUMPERS, TRACTOR_COMMENTS, HOIST_LIMIT_SWITCH, HOIST_MOTORS,HOIST_MOTOR_BRAKE,HOIST_LOAD_BRAKE, HOIST_GEAR_BOX, HOIST_UPPER_BLOCK, HOIST_LOWER_BLOCK, HOIST_SAFETY_LATCH, HOIST_HOOKS, HOIST_HOOK_TRAMS, HOIST_THROAT_TRAMS, HOIST_HOOK_SADDLE, HOIST_WIRE_ROPE_LOAD_CHAIN, HOIST_ROPE_CHAIN, HOIST_ROPE_DRUM, HOIST_CHAIN_LINKS,HOIST_CHAIN_CONTAINER, HOIST_HOLDING_BRAKES, HOIST_MECHANICAL_OPERATIONS,HOIST_MECHANICAL_INTERNAL, HOIST_VISUAL, HOIST_GEAR_CASE,HOIST_BEARINGS, HOIST_SEALS, HOIST_SUPPORTS, HOIST_GEARS,HOIST_PINIONS,HOIST_KEY_WAYS, HOIST_CUPLINGS,HOIST_UPPER_SHEAVE, HOIST_LUBRICATION, HOIST_BOLTS, HOIST_PHOTO, HOIST_COMMENTS, ELECTRIC_HOIST,ELECTRIC_MOTORS, ELECTRIC_SLIP_RINGS, ELECTRIC_COMMUTATOR,ELECTRIC_BRUSHES, ELECTRIC_ENCLOSURES, ELECTRIC_OPERATIONS,ELECTRIC_RESISTORS, ELECTRIC_SWITCHES, ELECTRIC_LOAD_LIMIT,ELECTRIC_WIRING, ELECTRIC_WIRING_COMMENTS, ELECTRIC_PHOTO, HOIST_ELECTRIC_COMMENTS, BRIDGE_END_TRUCKS,BRIDGE_WHEELS, BRIDGE_GIRDERS, BRIDGE_END_STOPS,BRIDGE_PHOTO, BRIDGE_COMMENTS, PENDANT_CONTROLS,DIRECTIONAL_LABELS, CABLE_CONTROLS, STRAIN_RELIEF_CABLE,HOIST_CONTROLS, RESISTOR_CONTROLS, FESTOON_CONTROLS, CONTROLS_PHOTO, CONTROLS_COMMENTS, MONO_RAIL_RAIL_JOINTS,MONO_RAIL_END_STOPS, MONO_RAIL_POWER_FEED, MONO_RAIL_CAPACITY, MONO_RAIL_PHOTO, MONO_RAIL_COMMENTS, RUN_WAY_RAILS, RUN_WAY_SUPPORT_BEAM, RUN_WAY_SUPPORT_PLATES, RUN_WAY_END_STOPS, RUN_WAY_PHOTO, RUN_WAY_RAIL_WEAR, RUN_WAY_COMMENTS,CRANE_ABOVE,CRANE_SIDES, CRANE_LOAD_TEST, CRANE_COMMENTS, CRANE_PHOTO, CRANE_DISCONNECT, CRANE_EXTRA_COMMENTS) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,%s)"""
            cur.execute(command,(crane_formid, crane_asset, address, city, submittername, submissiondate, serverdate, referencenumber, customername1, capacity, system_type, power, inspector, unitnumber, inspect_date, location, hoistmanufacturer, hoistserialnumber, modelnumber, approximateheight, basicinformationphoto, approximatespan, capacitymarkings, informationcomments, maincontractortest, bridgetest, testtrolleys, testhoists, testphoto, testcomments, pushbutton, warninglabel, functionlabels, labelcomments, festooncomments, generalcondition, festoontrack, cableconnections, pushbuttonphoto, pushbuttonstrainrelief, pushbuttoncomments, lowerhookcondition, lowerhooktrams, lowerhookthroat, lowerhooksaddle, lowerhooksphoto, lowerhookcomments, wireropecondition, wireropedia, numberofparts, wireropelubrication, wireropephoto, wireropechainlinks, wireropecomments, lowersafetylatch, lowersheaves, lowerkeeperplates, lowerthrustbearing, lowerbolts, lowersheavesbearings, lowersheaveguards, lowerblocksphoto, lowerblockscomments, cabvisibility, cabclearance, cabdriversseat, cabdoor, cabhousekeeping, cabsupports, cabfanheater, cabphoto,cabcomments, cabsafetylight, cabfireextinguisher, cabladder, cabsafetyphoto, cabsafetycomments, cabmastercontrollers, cabfunctionlabels, cabmainswitches, cabgeneralwiring, cabelectricphoto, cablighting, cabelectriccomments, bridgeflooring, bridgehandrails, bridgetoeplate, bridgeheadroom, bridgewalkwayphoto, bridgeopenings, bridgeconditiongeneral, bridgewalkwaycomments, girderconnections, bridgealignment, bridgerailclips, bridgegeneralwelds, bridgecamber, bridgetopplate, bridgeloadflanges, structurephoto, structurecomments, endtruckconnections, endtrucksafetylugs, endtruckbumpers, endtrucksweeperplates, endtruckphoto, endtruckwheels, endtruckbearings, endtruckcomments, driveoilseal, drivegearbox, drivegears, drivekeyways, driveseals, drivesupports, drivebearing, drivepinions, bridgedrivephoto, drivebolts, drivebrakes, bridgedrivecomments, bridgemotors, bridgesliprings, bridgecommutor, bridgebrushes, bridgecovers, bridgemotorbearings, bridgedisconnect, bridgehornbell, bridgehorncomments, bridgegeneralconduits, bridgecontrolenclosure, bridgecontroloperations, bridgeresistors, bridgetrolleyconductor, bridgeconductor, bridgeconductorcomments, bridgedisconnectphoto, bridgeinsulators, bridgecollectorpoles, bridgeelectriccomments, trolleyconnections, trolleyhoistconnections, trolleygeneralwelds, trolleysupports, trolleybumpers, trolleybumpercomments, trolleywheels, trolleywheelgears, trolleyphoto, trolleyseallubrication, trolleycapacitymarkings, trolleystructurecomments, trolleydisconnect, trolleymotors, trolleysliprings, trolleycommutator, trolleyholders,trolleymotorbearing, trolleywiringandconduits, trolleycontrolenclosure, trolleyelectricphoto, trolleycontroloperations, trolleyresistors, trolleyelectriccomments, tractorphoto, tractorwheelgauge, tractorbumpers, tractorcomments, hoistlimitswitch, hoistmotors, hoistmotorbrake, hoistloadbrake, hoistgearbox, hoistupperblock, hoistlowerblock, hoistsafetylatch, hoisthooks, hoisthooktrams, hoistthroattrams, hoisthooksaddle, hoistwireropeloadchain, hoistropechain, hoistropedrum, hoistchainlinks, hoistchaincontainer, hoistholdingbrakes, hoistmechanicaloperations, hoistmechanicalinternal, hoistvisual, hoistgearcase, hoistbearings, hoistseals, hoistsupports, hoistgears, hoistpinions, hoistkeyways, hoistcuplings, hoistuppersheave, hoistlubrication, hoistbolts, hoistphoto, hoistcomments, electrichoist, electricmotors, electricsliprings, electriccommutator, electricbrushes, electricenclosures, electricoperations, electricresistors, electricswitches, electricloadlimit, electricwiring, electricwiringcomments, electricphoto, hoistelectriccomments, bridgeendtrucks, bridgewheels, bridgegirders, bridgeendstops, bridgephoto, bridgecomments, pendantcontrols, directionallabels, cablecontrols, strainreliefcable, hoistcontrols, resistorcontrols, festooncontrols, controlsphoto, controlscomments, monorailrailjoints, monorailendstops, monorailpowerfeed, monorailcapacity, monorailphoto, monorailcomments, runwayrails, runwaysupportbeam, runwaysupportplates, runwayendstops, runwayphoto, runwayrailwear, runwaycomments, craneabove, cranesides, craneloadtest, cranecomments, cranephoto, cranedisconnect, craneextracomments))
            conn.commit()
            conn.close()

            return json.dumps({'success':True}), 200, {'ContentType':'application/json'}

        elif "cancel" in request.form:
            inspectiondate = datetime.today().strftime('%Y-%m-%d')
            print("refresh")
            return render_template('newform.html', inspectiondate=inspectiondate)

        elif "next" in request.form and checklist=='calipers':
            select_2 = "selected"
            return render_template('calipers.html',customername=customername, location=location, order=order, assetno=assetno, asset=asset, producttype=product, inspector = operator, inspectiontype=inspection, inspectiondate=date, salesmen=salesmen,size=size,length=length,wll=wll,result=result,comments=comment, select_1 = select_1, select_2 = select_2, select_3 = select_3, select_4 = select_4, select_5 = select_5, select_6 = select_6, select_1_1 = select_1_1, select_1_2 = select_1_2, select_1_3 = select_1_3, select_1_4 = select_1_4, select_1_5 = select_1_5 )

        elif "next" in request.form and checklist=='forklift':
            select_3 = "selected"
            return render_template('forklift.html',customername=customername, location=location, order=order, assetno=assetno, asset=asset, producttype=product, inspector = operator, inspectiontype=inspection, inspectiondate=date, salesmen=salesmen,size=size,length=length,wll=wll,result=result,comments=comment, select_1 = select_1, select_2 = select_2, select_3 = select_3, select_4 = select_4, select_5 = select_5, select_6 = select_6 ,select_1_1 = select_1_1, select_1_2 = select_1_2, select_1_3 = select_1_3, select_1_4 = select_1_4, select_1_5 = select_1_5)

        elif "next" in request.form and checklist=='fire':
            select_6 = "selected"
            return render_template('fire_protection.html',customername=customername, location=location, order=order, assetno=assetno, asset=asset, producttype=product, inspector = operator, inspectiontype=inspection, inspectiondate=date, salesmen=salesmen,size=size,length=length,wll=wll,result=result,comments=comment, select_1 = select_1, select_2 = select_2, select_3 = select_3, select_4 = select_4, select_5 = select_5, select_6 = select_6, select_1_1 = select_1_1, select_1_2 = select_1_2, select_1_3 = select_1_3, select_1_4 = select_1_4, select_1_5 = select_1_5)

        elif "next" in request.form and checklist=='crane':
            select_5 = "selected"
            return render_template('crane.html',customername=customername, location=location, order=order, assetno=assetno, asset=asset, producttype=product, inspector = operator, inspectiontype=inspection, inspectiondate=date, salesmen=salesmen,size=size,length=length,wll=wll,result=result,comments=comment, select_1 = select_1, select_2 = select_2, select_3 = select_3, select_4 = select_4, select_5 = select_5, select_6 = select_6, select_1_1 = select_1_1, select_1_2 = select_1_2, select_1_3 = select_1_3, select_1_4 = select_1_4, select_1_5 = select_1_5)

        elif "next" in request.form and checklist=='micro':
            select_4 = "selected"
            return render_template('micrometer.html',customername=customername, location=location, order=order, assetno=assetno, asset=asset, producttype=product, inspector = operator, inspectiontype=inspection, inspectiondate=date, salesmen=salesmen,size=size,length=length,wll=wll,result=result,comments=comment, select_1 = select_1, select_2 = select_2, select_3 = select_3, select_4 = select_4, select_5 = select_5, select_6 = select_6, select_1_1 = select_1_1, select_1_2 = select_1_2, select_1_3 = select_1_3, select_1_4 = select_1_4, select_1_5 = select_1_5)

        elif "next" in request.form and checklist=="nothing":
            select_1 = "selected"
            return render_template('newform.html',customername=customername, location=location, order=order, assetno=assetno, asset=asset, producttype=product, inspector = operator, inspectiontype=inspection, inspectiondate=date, salesmen=salesmen,size=size,length=length,wll=wll,result=result,comments=comment, select_1 = select_1, select_2 = select_2, select_3 = select_3, select_4 = select_4, select_5 = select_5, select_6 = select_6, select_1_1 = select_1_1, select_1_2 = select_1_2, select_1_3 = select_1_3, select_1_4 = select_1_4, select_1_5 = select_1_5)
        else:
            inspectiondate = datetime.today().strftime('%Y-%m-%d')
            return render_template('newform.html', inspectiondate=inspectiondate)
            pass

    elif request.method =='GET':
        inspectiondate = datetime.today().strftime('%Y-%m-%d')
        print("refresh")
        return render_template('newform.html', inspectiondate=inspectiondate)
        pass

    else:
        inspectiondate = datetime.today().strftime('%Y-%m-%d')
        print("refresh")
        return render_template('newform.html', inspectiondate=inspectiondate)
        pass

@app.route('/nextinspection', methods=['GET','POST'])
def render_plot():
    name = request.args.get('name')
    loc = request.args.get('loc')
    order = request.args.get('order')
    inspector = request.args.get('inspector')
    inspection = request.args.get('inspectiondate')
    salesmen = request.args.get('salesmen')
    product = request.args.get('producttype')
    #print(age)
    return render_template('newform.html',customername=name,location=loc,order=order,inspector=inspector,salesmen=salesmen,inspectiondate=inspection,producttype=product)


@app.route('/resetform', methods=['GET','POST'])
def resetform():
    if request.method == 'POST':
        print("reset form")
        if "cancel" in request.form:
            print("cancel")
            return render_template('newform.html')

        elif "next" in request.form:
            print("next")
            customername = request.form['customername']
            location = request.form['location']
            return render_template('newform.html',customername=customername, location=location)

        else:
            return render_template('newform.html')
            pass

    else:
        return render_template('newform.html')
        pass


@app.route('/update', methods=['GET','POST'])
def update():
    if request.method == 'POST':

        if "reset" in request.form:
            return render_template('update.html')

        elif "submit" in request.form:

            result=""
            user_email = request.form['user_email']
            print(user_email)
            customername = request.form['customername']
            location = request.form['location']
            order = request.form['order']
            assetno = request.form['assetno']
            asset = request.form['asset']
            product = request.form['producttype']
            inspector = request.form['inspector']
            inspection = request.form['inspectiontype']
            date = request.form['inspectiondate']
            salesmen = request.form['salesmen']
            size = request.form['size']
            length = request.form['length']
            wll = request.form['wll']
            results = request.form['result']
            comment = request.form['comments']
            serialno = request.form['serial']
            checklist = request.form['checklist']
            due_date = request.form['duedate']
            due_date = datetime.strptime(due_date,'%Y-%m-%d').strftime('%Y-%m-%d')
            date_format = datetime.strptime(date,'%Y-%m-%d').strftime('%Y-%m-%d')

            try:
                conn =  mysql.connector.connect(host=ENDPOINT, user=USR, passwd=token, port=PORT, database=DBNAME)
                cur = conn.cursor()
                command = """SELECT * FROM INSPECTIONS WHERE CUSTOMER_NAME = %s AND ASSETNO = %s AND INSPECTION_DATE = %s AND LOCATION = %s"""
                cur.execute(command,(customername,assetno,date_format,location))
                record = cur.fetchall()
                desc = cur.description
                column_names = [col[0] for col in desc]
                data = [dict(zip(column_names, row))  for row in record]
                conn.commit()
                conn.close()
                #print(len(record))
                if len(record) == 0:
                    return json.dumps({'success':False}), 200, {'ContentType':'application/json'}
                else:
                    conn =  mysql.connector.connect(host=ENDPOINT, user=USR, passwd=token, port=PORT, database=DBNAME)
                    cur = conn.cursor()
                    command = """ UPDATE INSPECTIONS SET ASSETNO = %s, CUSTOMER_NAME = %s, LOCATION = %s, ORDERNO = %s, ASSET_DESCRIPTION = %s, PRODUCT_TYPE = %s, INSPECTOR = %s, INSPECTION_TYPE = %s, INSPECTION_DATE = %s, SALESMEN = %s, SIZE =%s, LENGTH = %s, WLL=%s, RESULT = %s, COMMENTS =%s, SERIALNO =%s, CHECKLIST_NAME=%s, DUE_DATE=%s WHERE CUSTOMER_NAME=%s AND LOCATION = %s AND ASSETNO = %s AND INSPECTION_DATE = %s"""
                    cur.execute(command,(assetno, customername, location, order, asset, product, inspector, inspection, date_format, salesmen, size, length, wll ,results, comment, serialno, checklist, due_date,customername,location,assetno,date_format))
                    conn.commit()
                    conn.close()
                    return json.dumps({'success':True}), 200, {'ContentType':'application/json'}

            except Exception as e:
                print("Database connection failed due to {}".format(e))
                return json.dumps({'success':False}), 200, {'ContentType':'application/json'}

        elif "load" in request.form:
            load_ref = db.collection(u'inspections')
            cust = request.form['name']
            ass  = request.form['assetnum']
            dd   = request.form['date']
            date_format = datetime.strptime(dd,'%Y-%m-%d').strftime('%Y/%m/%d')
            loc  = request.form['address']

            load_query=load_ref.where(u'customer_name',u'==',cust).where(u'assetno',u'==',ass).where(u'inspection_date',u'==',date_format).where(u'location',u'==',loc)
            docs=load_query.stream()
            for doc in docs:
                load = doc.to_dict()
            return render_template('update.html', customername=load['customer_name'], location=load['location'], order=load['orderno'], assetno=load['assetno'], asset=load['asset_description'], producttype=load['product_type'], inspector=load['inspector'], inspectiontype=load['inspection_type'], inspectiondate=dd, salesmen=load['salesmen'], size=load['size'], length=load['length'], wll=load['wll'], result = load['result'], comments=load['comments'])

        else:
            return render_template('update.html')
            pass

    else:
        return render_template('update.html')


@app.route('/load', methods=['GET','POST'])
def load():
    if request.method == 'POST':
        if "load" in request.form:
            print("load")
            cust = request.form['name']
            ass  = request.form['assetnum']
            dd   = request.form['date']
            email = request.form['email']
            print(email)
            date_format = datetime.strptime(dd,'%Y-%m-%d').strftime('%Y-%m-%d')
            loc  = request.form['address']
            conn =  mysql.connector.connect(host=ENDPOINT, user=USR, passwd=token, port=PORT, database=DBNAME)
            cur = conn.cursor()
            command = """SELECT * FROM INSPECTIONS WHERE CUSTOMER_NAME = %s AND ASSETNO = %s AND INSPECTION_DATE = %s AND LOCATION = %s"""
            cur.execute(command,(cust,ass,date_format,loc))
            record = cur.fetchall()
            desc = cur.description
            column_names = [col[0] for col in desc]
            data = [dict(zip(column_names, row))  for row in record]
            conn.commit()
            conn.close()
            select_1=""
            select_2=""
            select_3=""
            select_4=""
            res = data[0]['RESULT']
            check_list = data[0]['CHECKLIST_NAME']
            if res == "PASS":
                select_1 = "selected"
            elif res == "FAIL":
                select_2 = "selected"
            elif res == "REPAIR":
                select_3 = "selected"
            else:
                select_4 = "selected"

            select_1_1=""
            select_1_2=""
            select_1_3=""
            select_1_4=""
            select_1_5=""
            select_1_6=""
            if check_list == "nothing":
                select_1_1 = "selected"
            elif check_list == "calipers":
                select_1_2 = "selected"
            elif check_list == "forklift":
                select_1_3 = "selected"
            elif check_list == "micro":
                select_1_4 = "seleted"
            elif check_list == "crane":
                select_1_5 = "selected"
            else:
                select_1_6 = "selected"

            return render_template('update.html', serial=data[0]['SERIALNO'],duedate = data[0]['DUE_DATE'],customername=data[0]['CUSTOMER_NAME'], location=data[0]['LOCATION'], order=data[0]['ORDERNO'], assetno=data[0]['ASSETNO'], asset=data[0]['ASSET_DESCRIPTION'], producttype=data[0]['PRODUCT_TYPE'], inspector=data[0]['INSPECTOR'], inspectiontype=data[0]['INSPECTION_TYPE'], inspectiondate=dd, salesmen=data[0]['SALESMEN'], size=data[0]['SIZE'], length=data[0]['LENGTH'], wll=data[0]['WLL'], result = data[0]['RESULT'], comments=data[0]['COMMENTS'], select_1=select_1, select_2=select_2, select_3=select_3, select_4=select_4)
        else:
            return render_template('update.html')
            pass

    else:
        return render_template('previous.html')


@app.route('/previous', methods=['GET','POST'])
def previous():
    if request.method == 'POST':
        print("previous")
        if "reset" in request.form:
            return render_template('previous.html')

        elif "submit" in request.form:
            result=""
            email=request.form["email"]
            print(email)
            # email of the user
            # let me show you an example
            # its gives my email good perfect thats what i need
            # now the problem is I cant do the same thing on another function
            customername = request.form['customername']
            location = request.form['location']
            order = request.form['order']
            assetno = request.form['assetno']
            asset = request.form['asset']
            product = request.form['producttype']
            inspector = request.form['inspector']
            inspection = request.form['inspectiontype']
            date = request.form['inspectiondate']
            salesmen = request.form['salesmen']
            size = request.form['size']
            length = request.form['length']
            wll = request.form['wll']
            results = request.form['result']
            comment = request.form['comments']
            serialno = request.form['serial']
            checklist = request.form['checklist']
            due_date = request.form['duedate']
            due_date = datetime.strptime(due_date,'%Y-%m-%d').strftime('%Y-%m-%d')
            date_format = datetime.strptime(date,'%Y-%m-%d').strftime('%Y-%m-%d')

            try:
                conn =  mysql.connector.connect(host=ENDPOINT, user=USR, passwd=token, port=PORT, database=DBNAME)
                cur = conn.cursor()
                command = """SELECT * FROM INSPECTIONS WHERE CUSTOMER_NAME = %s AND ASSETNO = %s AND INSPECTION_DATE = %s AND LOCATION = %s"""
                cur.execute(command,(customername,assetno,date_format,location))
                record = cur.fetchall()
                desc = cur.description
                column_names = [col[0] for col in desc]
                data = [dict(zip(column_names, row))  for row in record]
                conn.commit()
                conn.close()
                #print(len(record))
                if len(record) == 0:
                    conn =  mysql.connector.connect(host=ENDPOINT, user=USR, passwd=token, port=PORT, database=DBNAME)
                    cur = conn.cursor()
                    formid = str(uuid.uuid4()).replace('-','')
                    command = """INSERT INTO INSPECTIONS (FORMID , ASSETNO, CUSTOMER_NAME, LOCATION, ORDERNO, ASSET_DESCRIPTION,  PRODUCT_TYPE, INSPECTOR, INSPECTION_TYPE, INSPECTION_DATE, SALESMEN, SIZE, LENGTH, WLL, RESULT, COMMENTS, SERIALNO, CHECKLIST_NAME, DUE_DATE) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
                    cur.execute(command,(formid, assetno, customername, location, order, asset, product, inspector, inspection, date_format, salesmen, size, length, wll ,results, comment, serialno, checklist, due_date))
                    conn.commit()
                    conn.close()
                else:
                    conn =  mysql.connector.connect(host=ENDPOINT, user=USR, passwd=token, port=PORT, database=DBNAME)
                    cur = conn.cursor()
                    command = """ UPDATE INSPECTIONS SET ASSETNO = %s, CUSTOMER_NAME = %s, LOCATION = %s, ORDERNO = %s, ASSET_DESCRIPTION = %s, PRODUCT_TYPE = %s, INSPECTOR = %s, INSPECTION_TYPE = %s, INSPECTION_DATE = %s, SALESMEN = %s, SIZE =%s, LENGTH = %s, WLL=%s, RESULT = %s, COMMENTS =%s, SERIALNO =%s, CHECKLIST_NAME=%s, DUE_DATE=%s WHERE CUSTOMER_NAME=%s AND LOCATION = %s AND ASSETNO = %s AND INSPECTION_DATE = %s"""
                    cur.execute(command,(assetno, customername, location, order, asset, product, inspector, inspection, date_format, salesmen, size, length, wll ,results, comment, serialno, checklist, due_date,customername,location,assetno,date_format))
                    conn.commit()
                    conn.close()
                return json.dumps({'success':True}), 200, {'ContentType':'application/json'}

            except Exception as e:
                print("Database connection failed due to {}".format(e))
                return json.dumps({'success':False}), 200, {'ContentType':'application/json'}

        elif "load" in request.form:
            load_ref = db.collection(u'inspections')
            cust = request.form['name']
            ass  = request.form['assetnum']
            dd   = request.form['date']
            date_format = datetime.strptime(dd,'%Y-%m-%d').strftime('%Y/%m/%d')
            loc  = request.form['address']

            load_query=load_ref.where(u'customer_name',u'==',cust).where(u'assetno',u'==',ass).where(u'inspection_date',u'==',date_format).where(u'location',u'==',loc)
            docs=load_query.stream()
            for doc in docs:
                load = doc.to_dict()
            return render_template('previous.html', customername=load['customer_name'], location=load['location'], order=load['orderno'], assetno=load['assetno'], asset=load['asset_description'], producttype=load['product_type'], inspector=load['inspector'], inspectiontype=load['inspection_type'], inspectiondate=dd, salesmen=load['salesmen'], size=load['size'], length=load['length'], wll=load['wll'], result = load['result'], comments=load['comments'])

        else:
            return render_template('previous.html')
            pass

    else:
        return render_template('previous.html')


@app.route('/load_previous', methods=['GET','POST'])
def load_previous():
    if request.method == 'POST':
        print("load_previous")
        if "load" in request.form:
            cust = request.form['name']
            ass  = request.form['assetnum']
            dd   = request.form['date']
            date_format = datetime.strptime(dd,'%Y-%m-%d').strftime('%Y-%m-%d')
            loc  = request.form['address']
            email=request.form['email']
            print(email)
            #load_query=load_ref.where(u'customer_name',u'==',cust).where(u'assetno',u'==',ass).where(u'inspection_date',u'==',date_format).where(u'location',u'==',loc)
            #docs=load_query.stream()
            conn =  mysql.connector.connect(host=ENDPOINT, user=USR, passwd=token, port=PORT, database=DBNAME)
            cur = conn.cursor()
            command = """SELECT * FROM INSPECTIONS WHERE CUSTOMER_NAME = %s AND ASSETNO = %s AND INSPECTION_DATE = %s AND LOCATION = %s"""
            cur.execute(command,(cust,ass,date_format,loc))
            record = cur.fetchall()
            desc = cur.description
            column_names = [col[0] for col in desc]
            data = [dict(zip(column_names, row))  for row in record]
            conn.commit()
            conn.close()
            select_1=""
            select_2=""
            select_3=""
            select_4=""
            res = data[0]['RESULT']
            check_list = data[0]['CHECKLIST_NAME']
            if res == "PASS":
                select_1 = "selected"
            elif res == "FAIL":
                select_2 = "selected"
            elif res == "REPAIR":
                select_3 = "selected"
            else:
                select_4 = "selected"

            select_1_1=""
            select_1_2=""
            select_1_3=""
            select_1_4=""
            select_1_5=""
            select_1_6=""
            if check_list == "nothing":
                select_1_1 = "selected"
            elif check_list == "calipers":
                select_1_2 = "selected"
            elif check_list == "forklift":
                select_1_3 = "selected"
            elif check_list == "micro":
                select_1_4 = "seleted"
            elif check_list == "crane":
                select_1_5 = "selected"
            else:
                select_1_6 = "selected"
            print(data)
            render_template('previous.html', serial=data[0]['SERIALNO'],duedate = data[0]['DUE_DATE'],customername=data[0]['CUSTOMER_NAME'], location=data[0]['LOCATION'], order=data[0]['ORDERNO'], assetno=data[0]['ASSETNO'], asset=data[0]['ASSET_DESCRIPTION'], producttype=data[0]['PRODUCT_TYPE'], inspector=data[0]['INSPECTOR'], inspectiontype=data[0]['INSPECTION_TYPE'], inspectiondate=dd, salesmen=data[0]['SALESMEN'], size=data[0]['SIZE'], length=data[0]['LENGTH'], wll=data[0]['WLL'], result = data[0]['RESULT'], comments=data[0]['COMMENTS'], select_1=select_1, select_2=select_2, select_3=select_3, select_4=select_4)
            return json.dumps({'success':True}), 200, {'ContentType':'application/json'}
        else:
            return render_template('previous.html')
            pass

    else:
        return render_template('previous.html')



@app.route('/certs', methods=['GET','POST'])
def certs():
    if request.method == 'POST':
        results=[]
        assetno = request.form['assetnumber']
        customername = request.form['customername']
        fromdate = request.form['fromdate']
        todate = request.form['todate']
        location = request.form['location']
        serialno = request.form['serialno']
        operator= request.form['operator']
        specimen = request.form['specimen']

        if 'reset' in request.form:
            y = results
            return render_template('certs.html',y=y)

        elif 'submit' in request.form:
            b = datetime.strptime(fromdate,'%Y-%m-%d').strftime('%Y/%m/%d')
            c = datetime.strptime(todate,'%Y-%m-%d').strftime('%Y/%m/%d')
            try:
                ano = request.form['assetnumber']
                cname = request.form['customername']
                loc = request.form['location']
                op = request.form['operator']
                sno = request.form['serialno']
                sp = request.form['specimen']

                conn =  mysql.connector.connect(host=ENDPOINT, user=USR, passwd=token, port=PORT, database=DBNAME)
                cur = conn.cursor()

                if sp=="" and sno =="" and ano == "" and cname =="" and loc =="" and op=="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b))
                elif sp=="" and sno =="" and ano == "" and cname =="" and loc =="" and op!="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND OPERATOR=%s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,op))
                elif sp=="" and sno =="" and ano == "" and cname =="" and loc !="" and op=="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc))
                elif sp=="" and sno =="" and ano == "" and cname =="" and loc !="" and op!="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND OPERATOR = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,op))

                elif sp=="" and sno =="" and ano == "" and cname !="" and loc =="" and op=="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CUSTOMER_NAME = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,cname))
                elif sp=="" and sno =="" and ano == "" and cname !="" and loc =="" and op!="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND OPERATOR = %s AND CUSTOMER_NAME = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,op,cname))
                elif sp=="" and sno =="" and ano == "" and cname !="" and loc !="" and op=="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND CUSTOMER_NAME = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b, loc,cname))
                elif sp=="" and sno =="" and ano == "" and cname !="" and loc !="" and op!="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND OPERATOR = %s AND CUSTOMER_NAME = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b, loc,op,cname))

                elif sp=="" and sno =="" and ano != "" and cname =="" and loc =="" and op=="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano))
                elif sp=="" and sno =="" and ano != "" and cname =="" and loc =="" and op!="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND OPERATOR = %s  ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,op))
                elif sp=="" and sno =="" and ano != "" and cname =="" and loc !="" and op=="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND CITY = %s  ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,loc))
                elif sp=="" and sno =="" and ano != "" and cname =="" and loc !="" and op!="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND CITY = %s AND OPERATOR = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,loc,op))

                elif sp=="" and sno =="" and ano != "" and cname !="" and loc =="" and op=="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND CUSTOMER_NAME = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,cname))
                elif sp=="" and sno =="" and ano != "" and cname !="" and loc =="" and op!="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s  AND ASSETNO = %s AND CUSTOMER_NAME = %s AND OPERATOR = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,cname,op))
                elif sp=="" and sno =="" and ano != "" and cname !="" and loc !="" and op=="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s  AND ASSETNO = %s AND CUSTOMER_NAME = %s AND CITY = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,cname,loc))
                elif sp=="" and sno =="" and ano != "" and cname !="" and loc !="" and op!="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s  AND ASSETNO = %s AND CUSTOMER_NAME = %s AND CITY = %s AND OPERATOR = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,cname,loc,op))

                elif sp=="" and sno !="" and ano == "" and cname =="" and loc =="" and op=="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,sno))
                elif sp=="" and sno !="" and ano == "" and cname =="" and loc =="" and op!="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND OPERATOR=%s AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,op,sno))
                elif sp=="" and sno !="" and ano == "" and cname =="" and loc !="" and op=="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,sno))
                elif sp=="" and sno !="" and ano == "" and cname =="" and loc !="" and op!="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND OPERATOR = %s AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,op,sno))

                elif sp=="" and sno !="" and ano == "" and cname !="" and loc =="" and op=="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CUSTOMER_NAME = %s AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,cname,sno))
                elif sp=="" and sno !="" and ano == "" and cname !="" and loc =="" and op!="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND OPERATOR = %s AND CUSTOMER_NAME = %s AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,op,cname,sno))
                elif sp=="" and sno !="" and ano == "" and cname !="" and loc !="" and op=="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND CUSTOMER_NAME = %s AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b, loc,cname,sno))
                elif sp=="" and sno !="" and ano == "" and cname !="" and loc !="" and op!="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND OPERATOR = %s AND CUSTOMER_NAME = %s AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b, loc,op,cname,sno))

                elif sp=="" and sno !="" and ano != "" and cname =="" and loc =="" and op=="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,sno))
                elif sp=="" and sno !="" and ano != "" and cname =="" and loc =="" and op!="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND OPERATOR = %s  AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,op,sno))
                elif sp=="" and sno !="" and ano != "" and cname =="" and loc !="" and op=="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND CITY = %s  AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,loc,sno))
                elif sp=="" and sno !="" and ano != "" and cname =="" and loc !="" and op!="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND CITY = %s AND OPERATOR = %s AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,loc,op,sno))

                elif sp=="" and sno !="" and ano != "" and cname !="" and loc =="" and op=="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,cname))
                elif sp=="" and sno !="" and ano != "" and cname !="" and loc =="" and op!="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s  AND ASSETNO = %s AND CUSTOMER_NAME = %s AND OPERATOR = %s AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,cname,op))
                elif sp=="" and sno !="" and ano != "" and cname !="" and loc !="" and op=="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s  AND ASSETNO = %s AND CUSTOMER_NAME = %s AND CITY = %s AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,cname,loc))
                elif sp=="" and sno !="" and ano != "" and cname !="" and loc !="" and op!="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s  AND ASSETNO = %s AND CUSTOMER_NAME = %s AND CITY = %s AND OPERATOR = %s AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,cname,loc,op))

                ##############################################
                #############################################
                ############################################
                #############################################
                ############################################

                elif sp!="" and sno =="" and ano == "" and cname =="" and loc =="" and op=="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,sp))
                elif sp!="" and sno =="" and ano == "" and cname =="" and loc =="" and op!="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND OPERATOR=%s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,op,sp))
                elif sp!="" and sno =="" and ano == "" and cname =="" and loc !="" and op=="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,sp))
                elif sp!="" and sno =="" and ano == "" and cname =="" and loc !="" and op!="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND OPERATOR = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,op,sp))

                elif sp!="" and sno =="" and ano == "" and cname !="" and loc =="" and op=="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CUSTOMER_NAME = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,cname,sp))
                elif sp!="" and sno =="" and ano == "" and cname !="" and loc =="" and op!="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND OPERATOR = %s AND CUSTOMER_NAME = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,op,cname,sp))
                elif sp!="" and sno =="" and ano == "" and cname !="" and loc !="" and op=="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND CUSTOMER_NAME = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b, loc,cname,sp))
                elif sp!="" and sno =="" and ano == "" and cname !="" and loc !="" and op!="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND OPERATOR = %s AND CUSTOMER_NAME = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b, loc,op,cname,sp))

                elif sp!="" and sno =="" and ano != "" and cname =="" and loc =="" and op=="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,sp))
                elif sp!="" and sno =="" and ano != "" and cname =="" and loc =="" and op!="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND OPERATOR = %s  AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,op,sp))
                elif sp!="" and sno =="" and ano != "" and cname =="" and loc !="" and op=="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND CITY = %s  AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,loc,sp))
                elif sp!="" and sno =="" and ano != "" and cname =="" and loc !="" and op!="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND CITY = %s AND OPERATOR = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,loc,op,sp))

                elif sp!="" and sno =="" and ano != "" and cname !="" and loc =="" and op=="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,cname,sp))
                elif sp!="" and sno =="" and ano != "" and cname !="" and loc =="" and op!="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s  AND ASSETNO = %s AND CUSTOMER_NAME = %s AND OPERATOR = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,cname,op,sp))
                elif sp!="" and sno =="" and ano != "" and cname !="" and loc !="" and op=="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s  AND ASSETNO = %s AND CUSTOMER_NAME = %s AND CITY = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,cname,loc,sp))
                elif sp!="" and sno =="" and ano != "" and cname !="" and loc !="" and op!="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s  AND ASSETNO = %s AND CUSTOMER_NAME = %s AND CITY = %s AND OPERATOR = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,cname,loc,op,sp))

                elif sp!="" and sno !="" and ano == "" and cname =="" and loc =="" and op=="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,sno,sp))
                elif sp!="" and sno !="" and ano == "" and cname =="" and loc =="" and op!="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND OPERATOR=%s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,op,sno,sp))
                elif sp!="" and sno !="" and ano == "" and cname =="" and loc !="" and op=="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,sno,sp))
                elif sp!="" and sno !="" and ano == "" and cname =="" and loc !="" and op!="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND OPERATOR = %s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,loc,op,sno,sp))

                elif sp!="" and sno !="" and ano == "" and cname !="" and loc =="" and op=="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CUSTOMER_NAME = %s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,cname,sno,sp))
                elif sp!="" and sno !="" and ano == "" and cname !="" and loc =="" and op!="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND OPERATOR = %s AND CUSTOMER_NAME = %s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,op,cname,sno,sp))
                elif sp!="" and sno !="" and ano == "" and cname !="" and loc !="" and op=="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND CUSTOMER_NAME = %s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b, loc,cname,sno,sp))
                elif sp!="" and sno !="" and ano == "" and cname !="" and loc !="" and op!="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND OPERATOR = %s AND CUSTOMER_NAME = %s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b, loc,op,cname,sno,sp))

                elif sp!="" and sno !="" and ano != "" and cname =="" and loc =="" and op=="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,sno,sp))
                elif sp!="" and sno !="" and ano != "" and cname =="" and loc =="" and op!="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND OPERATOR = %s  AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,op,sno,sp))
                elif sp!="" and sno !="" and ano != "" and cname =="" and loc !="" and op=="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND CITY = %s  AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,loc,sno,sp))
                elif sp!="" and sno !="" and ano != "" and cname =="" and loc !="" and op!="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND CITY = %s AND OPERATOR = %s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,loc,op,sno,sp))

                elif sp!="" and sno !="" and ano != "" and cname !="" and loc =="" and op=="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,cname,sp))
                elif sp!="" and sno !="" and ano != "" and cname !="" and loc =="" and op!="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s  AND ASSETNO = %s AND CUSTOMER_NAME = %s AND OPERATOR = %s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,cname,op,sp))
                elif sp!="" and sno !="" and ano != "" and cname !="" and loc !="" and op=="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s  AND ASSETNO = %s AND CUSTOMER_NAME = %s AND CITY = %s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,cname,loc,sp))
                elif sp!="" and sno !="" and ano != "" and cname !="" and loc !="" and op!="":
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s  AND ASSETNO = %s AND CUSTOMER_NAME = %s AND CITY = %s AND OPERATOR = %s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,cname,loc,op,sp))

                else:
                    command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s  AND ASSETNO = %s AND CUSTOMER_NAME = %s AND CITY = %s AND OPERATOR = %s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                    cur.execute(command,(c,b,ano,cname,loc,op,sp))
                desc = cur.description
                column_names = [col[0] for col in desc]
                data = [dict(zip(column_names, row))for row in cur.fetchall()]
                conn.commit()
                conn.close()
                #print(data)
                results = data
                y = data

                return render_template('certs.html',assetnumber=ano, operator=op, customername=cname, fromdate=fromdate, todate=todate,tbl = results, location=loc,serialno=sno,specimen=sp, y=y)

            except Exception as e:
                print("Database connection failed due to {}".format(e))
                data = []
                results = data
                y = data
                #return json.dumps({'success':False}), 200, {'ContentType':'application/json'}
                return render_template('certs.html',assetnumber=ano, customername=cname, fromdate=fromdate, todate=todate,tbl = results, location=loc,serialno=sno,operator=op,specimen=sp, y=y)

        elif "report" in request.form:
            b = datetime.strptime(fromdate,'%Y-%m-%d').strftime('%Y/%m/%d')
            c = datetime.strptime(todate,'%Y-%m-%d').strftime('%Y/%m/%d')
            ano = request.form['assetnumber']
            cname = request.form['customername']
            loc = request.form['location']
            op = request.form['operator']
            sno = request.form['serialno']
            sp = request.form['specimen']

            conn =  mysql.connector.connect(host=ENDPOINT, user=USR, passwd=token, port=PORT, database=DBNAME)
            cur = conn.cursor()

            if sp=="" and sno =="" and ano == "" and cname =="" and loc =="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b))
            elif sp=="" and sno =="" and ano == "" and cname =="" and loc =="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND OPERATOR=%s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,op))
            elif sp=="" and sno =="" and ano == "" and cname =="" and loc !="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,loc))
            elif sp=="" and sno =="" and ano == "" and cname =="" and loc !="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND OPERATOR = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,loc,op))

            elif sp=="" and sno =="" and ano == "" and cname !="" and loc =="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CUSTOMER_NAME = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,cname))
            elif sp=="" and sno =="" and ano == "" and cname !="" and loc =="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND OPERATOR = %s AND CUSTOMER_NAME = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,op,cname))
            elif sp=="" and sno =="" and ano == "" and cname !="" and loc !="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND CUSTOMER_NAME = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b, loc,cname))
            elif sp=="" and sno =="" and ano == "" and cname !="" and loc !="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND OPERATOR = %s AND CUSTOMER_NAME = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b, loc,op,cname))

            elif sp=="" and sno =="" and ano != "" and cname =="" and loc =="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano))
            elif sp=="" and sno =="" and ano != "" and cname =="" and loc =="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND OPERATOR = %s  ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,op))
            elif sp=="" and sno =="" and ano != "" and cname =="" and loc !="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND CITY = %s  ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,loc))
            elif sp=="" and sno =="" and ano != "" and cname =="" and loc !="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND CITY = %s AND OPERATOR = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,loc,op))

            elif sp=="" and sno =="" and ano != "" and cname !="" and loc =="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND CUSTOMER_NAME = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,cname))
            elif sp=="" and sno =="" and ano != "" and cname !="" and loc =="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s  AND ASSETNO = %s AND CUSTOMER_NAME = %s AND OPERATOR = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,cname,op))
            elif sp=="" and sno =="" and ano != "" and cname !="" and loc !="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s  AND ASSETNO = %s AND CUSTOMER_NAME = %s AND CITY = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,cname,loc))
            elif sp=="" and sno =="" and ano != "" and cname !="" and loc !="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s  AND ASSETNO = %s AND CUSTOMER_NAME = %s AND CITY = %s AND OPERATOR = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,cname,loc,op))

            elif sp=="" and sno !="" and ano == "" and cname =="" and loc =="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,sno))
            elif sp=="" and sno !="" and ano == "" and cname =="" and loc =="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND OPERATOR=%s AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,op,sno))
            elif sp=="" and sno !="" and ano == "" and cname =="" and loc !="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,loc,sno))
            elif sp=="" and sno !="" and ano == "" and cname =="" and loc !="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND OPERATOR = %s AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,loc,op,sno))

            elif sp=="" and sno !="" and ano == "" and cname !="" and loc =="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CUSTOMER_NAME = %s AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,cname,sno))
            elif sp=="" and sno !="" and ano == "" and cname !="" and loc =="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND OPERATOR = %s AND CUSTOMER_NAME = %s AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,op,cname,sno))
            elif sp=="" and sno !="" and ano == "" and cname !="" and loc !="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND CUSTOMER_NAME = %s AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b, loc,cname,sno))
            elif sp=="" and sno !="" and ano == "" and cname !="" and loc !="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND OPERATOR = %s AND CUSTOMER_NAME = %s AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b, loc,op,cname,sno))

            elif sp=="" and sno !="" and ano != "" and cname =="" and loc =="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,sno))
            elif sp=="" and sno !="" and ano != "" and cname =="" and loc =="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND OPERATOR = %s  AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,op,sno))
            elif sp=="" and sno !="" and ano != "" and cname =="" and loc !="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND CITY = %s  AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,loc,sno))
            elif sp=="" and sno !="" and ano != "" and cname =="" and loc !="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND CITY = %s AND OPERATOR = %s AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,loc,op,sno))

            elif sp=="" and sno !="" and ano != "" and cname !="" and loc =="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,cname))
            elif sp=="" and sno !="" and ano != "" and cname !="" and loc =="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s  AND ASSETNO = %s AND CUSTOMER_NAME = %s AND OPERATOR = %s AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,cname,op))
            elif sp=="" and sno !="" and ano != "" and cname !="" and loc !="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s  AND ASSETNO = %s AND CUSTOMER_NAME = %s AND CITY = %s AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,cname,loc))
            elif sp=="" and sno !="" and ano != "" and cname !="" and loc !="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s  AND ASSETNO = %s AND CUSTOMER_NAME = %s AND CITY = %s AND OPERATOR = %s AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,cname,loc,op))

            ##############################################
            #############################################
            ############################################
            #############################################
            ############################################

            elif sp!="" and sno =="" and ano == "" and cname =="" and loc =="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,sp))
            elif sp!="" and sno =="" and ano == "" and cname =="" and loc =="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND OPERATOR=%s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,op,sp))
            elif sp!="" and sno =="" and ano == "" and cname =="" and loc !="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,loc,sp))
            elif sp!="" and sno =="" and ano == "" and cname =="" and loc !="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND OPERATOR = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,loc,op,sp))

            elif sp!="" and sno =="" and ano == "" and cname !="" and loc =="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CUSTOMER_NAME = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,cname,sp))
            elif sp!="" and sno =="" and ano == "" and cname !="" and loc =="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND OPERATOR = %s AND CUSTOMER_NAME = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,op,cname,sp))
            elif sp!="" and sno =="" and ano == "" and cname !="" and loc !="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND CUSTOMER_NAME = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b, loc,cname,sp))
            elif sp!="" and sno =="" and ano == "" and cname !="" and loc !="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND OPERATOR = %s AND CUSTOMER_NAME = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b, loc,op,cname,sp))

            elif sp!="" and sno =="" and ano != "" and cname =="" and loc =="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,sp))
            elif sp!="" and sno =="" and ano != "" and cname =="" and loc =="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND OPERATOR = %s  AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,op,sp))
            elif sp!="" and sno =="" and ano != "" and cname =="" and loc !="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND CITY = %s  AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,loc,sp))
            elif sp!="" and sno =="" and ano != "" and cname =="" and loc !="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND CITY = %s AND OPERATOR = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,loc,op,sp))

            elif sp!="" and sno =="" and ano != "" and cname !="" and loc =="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,cname,sp))
            elif sp!="" and sno =="" and ano != "" and cname !="" and loc =="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s  AND ASSETNO = %s AND CUSTOMER_NAME = %s AND OPERATOR = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,cname,op,sp))
            elif sp!="" and sno =="" and ano != "" and cname !="" and loc !="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s  AND ASSETNO = %s AND CUSTOMER_NAME = %s AND CITY = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,cname,loc,sp))
            elif sp!="" and sno =="" and ano != "" and cname !="" and loc !="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s  AND ASSETNO = %s AND CUSTOMER_NAME = %s AND CITY = %s AND OPERATOR = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,cname,loc,op,sp))

            elif sp!="" and sno !="" and ano == "" and cname =="" and loc =="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,sno,sp))
            elif sp!="" and sno !="" and ano == "" and cname =="" and loc =="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND OPERATOR=%s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,op,sno,sp))
            elif sp!="" and sno !="" and ano == "" and cname =="" and loc !="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,loc,sno,sp))
            elif sp!="" and sno !="" and ano == "" and cname =="" and loc !="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND OPERATOR = %s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,loc,op,sno,sp))

            elif sp!="" and sno !="" and ano == "" and cname !="" and loc =="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CUSTOMER_NAME = %s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,cname,sno,sp))
            elif sp!="" and sno !="" and ano == "" and cname !="" and loc =="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND OPERATOR = %s AND CUSTOMER_NAME = %s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,op,cname,sno,sp))
            elif sp!="" and sno !="" and ano == "" and cname !="" and loc !="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND CUSTOMER_NAME = %s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b, loc,cname,sno,sp))
            elif sp!="" and sno !="" and ano == "" and cname !="" and loc !="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND OPERATOR = %s AND CUSTOMER_NAME = %s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b, loc,op,cname,sno,sp))

            elif sp!="" and sno !="" and ano != "" and cname =="" and loc =="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,sno,sp))
            elif sp!="" and sno !="" and ano != "" and cname =="" and loc =="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND OPERATOR = %s  AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,op,sno,sp))
            elif sp!="" and sno !="" and ano != "" and cname =="" and loc !="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND CITY = %s  AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,loc,sno,sp))
            elif sp!="" and sno !="" and ano != "" and cname =="" and loc !="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND CITY = %s AND OPERATOR = %s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,loc,op,sno,sp))

            elif sp!="" and sno !="" and ano != "" and cname !="" and loc =="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,cname,sp))
            elif sp!="" and sno !="" and ano != "" and cname !="" and loc =="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s  AND ASSETNO = %s AND CUSTOMER_NAME = %s AND OPERATOR = %s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,cname,op,sp))
            elif sp!="" and sno !="" and ano != "" and cname !="" and loc !="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s  AND ASSETNO = %s AND CUSTOMER_NAME = %s AND CITY = %s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,cname,loc,sp))
            elif sp!="" and sno !="" and ano != "" and cname !="" and loc !="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s  AND ASSETNO = %s AND CUSTOMER_NAME = %s AND CITY = %s AND OPERATOR = %s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,cname,loc,op,sp))

            else:
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s  AND ASSETNO = %s AND CUSTOMER_NAME = %s AND CITY = %s AND OPERATOR = %s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,cname,loc,op,sp))
            desc = cur.description
            column_names = [col[0] for col in desc]
            data = [dict(zip(column_names, row))for row in cur.fetchall()]
            conn.commit()
            conn.close()
            #print(data)
            results = data
            generate_reports(results)
            return send_file("/Users/gunam/Desktop/flask/inspection.xlsx", as_attachment=True)

        elif 'download' in request.form:
            b = datetime.strptime(fromdate,'%Y-%m-%d').strftime('%Y/%m/%d')
            c = datetime.strptime(todate,'%Y-%m-%d').strftime('%Y/%m/%d')
            ano = request.form['assetnumber']
            cname = request.form['customername']
            loc = request.form['location']
            op = request.form['operator']
            sno = request.form['serialno']
            sp = request.form['specimen']

            conn =  mysql.connector.connect(host=ENDPOINT, user=USR, passwd=token, port=PORT, database=DBNAME)
            cur = conn.cursor()

            if sp=="" and sno =="" and ano == "" and cname =="" and loc =="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b))
            elif sp=="" and sno =="" and ano == "" and cname =="" and loc =="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND OPERATOR=%s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,op))
            elif sp=="" and sno =="" and ano == "" and cname =="" and loc !="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,loc))
            elif sp=="" and sno =="" and ano == "" and cname =="" and loc !="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND OPERATOR = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,loc,op))

            elif sp=="" and sno =="" and ano == "" and cname !="" and loc =="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CUSTOMER_NAME = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,cname))
            elif sp=="" and sno =="" and ano == "" and cname !="" and loc =="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND OPERATOR = %s AND CUSTOMER_NAME = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,op,cname))
            elif sp=="" and sno =="" and ano == "" and cname !="" and loc !="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND CUSTOMER_NAME = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b, loc,cname))
            elif sp=="" and sno =="" and ano == "" and cname !="" and loc !="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND OPERATOR = %s AND CUSTOMER_NAME = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b, loc,op,cname))

            elif sp=="" and sno =="" and ano != "" and cname =="" and loc =="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano))
            elif sp=="" and sno =="" and ano != "" and cname =="" and loc =="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND OPERATOR = %s  ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,op))
            elif sp=="" and sno =="" and ano != "" and cname =="" and loc !="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND CITY = %s  ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,loc))
            elif sp=="" and sno =="" and ano != "" and cname =="" and loc !="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND CITY = %s AND OPERATOR = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,loc,op))

            elif sp=="" and sno =="" and ano != "" and cname !="" and loc =="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND CUSTOMER_NAME = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,cname))
            elif sp=="" and sno =="" and ano != "" and cname !="" and loc =="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s  AND ASSETNO = %s AND CUSTOMER_NAME = %s AND OPERATOR = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,cname,op))
            elif sp=="" and sno =="" and ano != "" and cname !="" and loc !="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s  AND ASSETNO = %s AND CUSTOMER_NAME = %s AND CITY = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,cname,loc))
            elif sp=="" and sno =="" and ano != "" and cname !="" and loc !="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s  AND ASSETNO = %s AND CUSTOMER_NAME = %s AND CITY = %s AND OPERATOR = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,cname,loc,op))

            elif sp=="" and sno !="" and ano == "" and cname =="" and loc =="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,sno))
            elif sp=="" and sno !="" and ano == "" and cname =="" and loc =="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND OPERATOR=%s AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,op,sno))
            elif sp=="" and sno !="" and ano == "" and cname =="" and loc !="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,loc,sno))
            elif sp=="" and sno !="" and ano == "" and cname =="" and loc !="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND OPERATOR = %s AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,loc,op,sno))

            elif sp=="" and sno !="" and ano == "" and cname !="" and loc =="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CUSTOMER_NAME = %s AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,cname,sno))
            elif sp=="" and sno !="" and ano == "" and cname !="" and loc =="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND OPERATOR = %s AND CUSTOMER_NAME = %s AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,op,cname,sno))
            elif sp=="" and sno !="" and ano == "" and cname !="" and loc !="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND CUSTOMER_NAME = %s AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b, loc,cname,sno))
            elif sp=="" and sno !="" and ano == "" and cname !="" and loc !="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND OPERATOR = %s AND CUSTOMER_NAME = %s AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b, loc,op,cname,sno))

            elif sp=="" and sno !="" and ano != "" and cname =="" and loc =="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,sno))
            elif sp=="" and sno !="" and ano != "" and cname =="" and loc =="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND OPERATOR = %s  AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,op,sno))
            elif sp=="" and sno !="" and ano != "" and cname =="" and loc !="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND CITY = %s  AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,loc,sno))
            elif sp=="" and sno !="" and ano != "" and cname =="" and loc !="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND CITY = %s AND OPERATOR = %s AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,loc,op,sno))

            elif sp=="" and sno !="" and ano != "" and cname !="" and loc =="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,cname))
            elif sp=="" and sno !="" and ano != "" and cname !="" and loc =="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s  AND ASSETNO = %s AND CUSTOMER_NAME = %s AND OPERATOR = %s AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,cname,op))
            elif sp=="" and sno !="" and ano != "" and cname !="" and loc !="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s  AND ASSETNO = %s AND CUSTOMER_NAME = %s AND CITY = %s AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,cname,loc))
            elif sp=="" and sno !="" and ano != "" and cname !="" and loc !="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s  AND ASSETNO = %s AND CUSTOMER_NAME = %s AND CITY = %s AND OPERATOR = %s AND SERIALNO = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,cname,loc,op))

            ##############################################
            #############################################
            ############################################
            #############################################
            ############################################

            elif sp!="" and sno =="" and ano == "" and cname =="" and loc =="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,sp))
            elif sp!="" and sno =="" and ano == "" and cname =="" and loc =="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND OPERATOR=%s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,op,sp))
            elif sp!="" and sno =="" and ano == "" and cname =="" and loc !="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,loc,sp))
            elif sp!="" and sno =="" and ano == "" and cname =="" and loc !="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND OPERATOR = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,loc,op,sp))

            elif sp!="" and sno =="" and ano == "" and cname !="" and loc =="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CUSTOMER_NAME = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,cname,sp))
            elif sp!="" and sno =="" and ano == "" and cname !="" and loc =="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND OPERATOR = %s AND CUSTOMER_NAME = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,op,cname,sp))
            elif sp!="" and sno =="" and ano == "" and cname !="" and loc !="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND CUSTOMER_NAME = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b, loc,cname,sp))
            elif sp!="" and sno =="" and ano == "" and cname !="" and loc !="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND OPERATOR = %s AND CUSTOMER_NAME = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b, loc,op,cname,sp))

            elif sp!="" and sno =="" and ano != "" and cname =="" and loc =="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,sp))
            elif sp!="" and sno =="" and ano != "" and cname =="" and loc =="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND OPERATOR = %s  AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,op,sp))
            elif sp!="" and sno =="" and ano != "" and cname =="" and loc !="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND CITY = %s  AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,loc,sp))
            elif sp!="" and sno =="" and ano != "" and cname =="" and loc !="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND CITY = %s AND OPERATOR = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,loc,op,sp))

            elif sp!="" and sno =="" and ano != "" and cname !="" and loc =="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,cname,sp))
            elif sp!="" and sno =="" and ano != "" and cname !="" and loc =="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s  AND ASSETNO = %s AND CUSTOMER_NAME = %s AND OPERATOR = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,cname,op,sp))
            elif sp!="" and sno =="" and ano != "" and cname !="" and loc !="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s  AND ASSETNO = %s AND CUSTOMER_NAME = %s AND CITY = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,cname,loc,sp))
            elif sp!="" and sno =="" and ano != "" and cname !="" and loc !="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s  AND ASSETNO = %s AND CUSTOMER_NAME = %s AND CITY = %s AND OPERATOR = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,cname,loc,op,sp))

            elif sp!="" and sno !="" and ano == "" and cname =="" and loc =="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,sno,sp))
            elif sp!="" and sno !="" and ano == "" and cname =="" and loc =="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND OPERATOR=%s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,op,sno,sp))
            elif sp!="" and sno !="" and ano == "" and cname =="" and loc !="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,loc,sno,sp))
            elif sp!="" and sno !="" and ano == "" and cname =="" and loc !="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND OPERATOR = %s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,loc,op,sno,sp))

            elif sp!="" and sno !="" and ano == "" and cname !="" and loc =="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CUSTOMER_NAME = %s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,cname,sno,sp))
            elif sp!="" and sno !="" and ano == "" and cname !="" and loc =="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND OPERATOR = %s AND CUSTOMER_NAME = %s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,op,cname,sno,sp))
            elif sp!="" and sno !="" and ano == "" and cname !="" and loc !="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND CUSTOMER_NAME = %s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b, loc,cname,sno,sp))
            elif sp!="" and sno !="" and ano == "" and cname !="" and loc !="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND CITY = %s AND OPERATOR = %s AND CUSTOMER_NAME = %s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b, loc,op,cname,sno,sp))

            elif sp!="" and sno !="" and ano != "" and cname =="" and loc =="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,sno,sp))
            elif sp!="" and sno !="" and ano != "" and cname =="" and loc =="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND OPERATOR = %s  AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,op,sno,sp))
            elif sp!="" and sno !="" and ano != "" and cname =="" and loc !="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND CITY = %s  AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,loc,sno,sp))
            elif sp!="" and sno !="" and ano != "" and cname =="" and loc !="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND CITY = %s AND OPERATOR = %s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,loc,op,sno,sp))

            elif sp!="" and sno !="" and ano != "" and cname !="" and loc =="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s AND ASSETNO = %s AND CUSTOMER_NAME = %s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,cname,sp))
            elif sp!="" and sno !="" and ano != "" and cname !="" and loc =="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s  AND ASSETNO = %s AND CUSTOMER_NAME = %s AND OPERATOR = %s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,cname,op,sp))
            elif sp!="" and sno !="" and ano != "" and cname !="" and loc !="" and op=="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s  AND ASSETNO = %s AND CUSTOMER_NAME = %s AND CITY = %s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,cname,loc,sp))
            elif sp!="" and sno !="" and ano != "" and cname !="" and loc !="" and op!="":
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s  AND ASSETNO = %s AND CUSTOMER_NAME = %s AND CITY = %s AND OPERATOR = %s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,cname,loc,op,sp))

            else:
                command = """SELECT * FROM TESTBED_CERTS WHERE TESTDATE <= %s AND TESTDATE >= %s  AND ASSETNO = %s AND CUSTOMER_NAME = %s AND CITY = %s AND OPERATOR = %s AND SERIALNO = %s AND SPECIMEN = %s ORDER BY STR_TO_DATE(TESTDATE, '%y-%m-%d')"""
                cur.execute(command,(c,b,ano,cname,loc,op,sp))
            desc = cur.description
            column_names = [col[0] for col in desc]
            data = [dict(zip(column_names, row))for row in cur.fetchall()]
            conn.commit()
            conn.close()
            results = data
            zipf = zipfile.ZipFile('TestCerts.zip','w', zipfile.ZIP_DEFLATED)

            pdf_name=[]
            for r in data:
                pdf_name.append(r['PDF_NAME'])

            for root,dirs, files in os.walk('/Users/gunam/Desktop/flask/static/Certs/'):
                for file in files:
                    if file in pdf_name:
                        src = '/Users/gunam/Desktop/flask/static/Certs/'+file
                        dst = '/Users/gunam/Desktop/flask/TestCerts/'
                        shutil.copy(src, dst)

            for root,dirs, files in os.walk('/Users/gunam/Desktop/flask/TestCerts/'):
                for file in files:
                    zipf.write('TestCerts/'+file)

            zipf.close()
            return send_file('TestCerts.zip',mimetype = 'zip',attachment_filename= 'TestCerts.zip',as_attachment = True)

        else:
            y = results
            return render_template('certs.html',y=y)
            pass
    else:
        results=[]
        y = results
        return render_template('certs.html',y=y)


@app.route('/downloadpdf/', methods=['GET','POST'])
def downloadpdf():
    idd = request.args.get('idd', default='', type=str)
    idd = idd.split("/")
    pdfdownload = "/Users/gunam/Desktop/flask/static/Certs/"+idd[-1]
    return send_file(pdfdownload, as_attachment=True)

@app.route('/downloadpdf1/', methods=['GET','POST'])
def downloadpdf1():
    idd = request.args.get('idd', default='', type=str)
    idd = idd.split("/")
    pdfdownload = "/Users/gunam/Desktop/flask/static/Reports/"+idd[-1]
    return send_file(pdfdownload, as_attachment=True)

@app.route('/calipers', methods=['GET','POST'])
def calipers():
    #print("inside calipers")
    if request.method == 'POST':
        print("inside calipers")
        return render_template('calipers.html')
    else:
        inspectiondate = datetime.today().strftime('%Y-%m-%d')
        return render_template('calipers.html', select_2 = "selected", inspectiondate=inspectiondate)

@app.route('/forklift', methods=['GET','POST'])
def forklift():
    #print("inside calipers")
    if request.method == 'POST':
        print("inside calipers")
        return render_template('forklift.html')
    else:
        inspectiondate = datetime.today().strftime('%Y-%m-%d')
        return render_template('forklift.html', select_3 = "selected", inspectiondate=inspectiondate)

@app.route('/micro', methods=['GET','POST'])
def micro():

    if request.method == 'POST':
        print("inside calipers")
        return render_template('micrometer.html')
    else:
        inspectiondate = datetime.today().strftime('%Y-%m-%d')
        return render_template('micrometer.html', select_4 = "selected", inspectiondate=inspectiondate)

@app.route('/crane', methods=['GET','POST'])
def crane():

    if request.method == 'POST':
        print("inside calipers")
        return render_template('crane.html')
    else:
        inspectiondate = datetime.today().strftime('%Y-%m-%d')
        return render_template('crane.html', select_5 = "selected", inspectiondate=inspectiondate)

@app.route('/fire', methods=['GET','POST'])
def fire():
    if request.method == 'POST':
        print("inside calipers")
        return render_template('fire_protection.html')
    else:
        inspectiondate = datetime.today().strftime('%Y-%m-%d')
        return render_template('fire_protection.html', select_6 = "selected", inspectiondate=inspectiondate)

@app.route('/nothing', methods=['GET','POST'])
def nothing():
    if request.method == 'POST':
        inspectiondate = datetime.today().strftime('%Y-%m-%d')
        return render_template('newform.html', inspectiondate=inspectiondate)
    else:
        inspectiondate = datetime.today().strftime('%Y-%m-%d')
        print("refresh")
        return render_template('newform.html', inspectiondate=inspectiondate)

if __name__ == "__main__":
    app.debug = True
    app.run()
