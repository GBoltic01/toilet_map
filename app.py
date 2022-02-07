from flask import Flask, render_template, url_for, request, redirect, flash, session, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from sqlalchemy import text
from geoalchemy2 import Geometry
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import Session
import geoalchemy2.functions as geofunc

import json, os, string, random


app = Flask(__name__) 

app.config['SQLALCHEMY_DATABASE_URI'] = 'xxx'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['MAIL_SERVER']='smtp.mailtrap.io'
app.config['MAIL_PORT'] = 2525
app.config['MAIL_USERNAME'] = 'xxx'
app.config['MAIL_PASSWORD'] = 'xxx'
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False

mail = Mail(app)

db = SQLAlchemy(app)

Base = automap_base()
Base.prepare(db.engine, reflect=True)
session = Session(db.engine)

Toilet = Base.classes.glasgow_toilets
Votes = Base.classes.votes

def add_points():
    query = db.session.query(geofunc.ST_AsGeoJSON(Toilet)).all()
    geojson_points = {
    "type": "FeatureCollection",
    "features": [json.loads(my_tuple[0]) for my_tuple in query]
    }
    return geojson_points



@app.route('/home', methods=['POST', 'GET'])
def index():
    
    
    with db.engine.connect() as con:
        con.execute("UPDATE glasgow_toilets t1 SET votes = t2.idcount FROM (SELECT  count(id) as idcount, id as id1 FROM votes GROUP BY id) as t2 WHERE id = t2.id1")
    
    
    
    random_string = ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in range(16))
    
    res = make_response()
    
    if 'unique-string' in request.cookies:
        cookies = request.cookies
        unique_string = cookies.get('unique-string')
    else: 
        res.set_cookie('unique-string', random_string, max_age=60*60*24*354*2)

    if request.method == 'POST':
        
        # Set all parameters that will be passed to DB from the modal survey
        
        location = request.form['location']
        free = request.form['free_of_charge']
        public = request.form['public']
        buy_product = request.form['buy_product']
        accessible = request.form['accessible']
        cleanliness = request.form['cleanliness']
        toiletries = request.form['toiletries']
        coordinates = request.form['coordinates']
        rating = request.form['overall-rating']
        other_comment = request.form['other-comments']
        unique_str = unique_string

        # Pass data to the DB and create new entry in glasgow_toilets table
        new_toilet = Toilet(cookie_str=unique_str, location_1=location, clean=cleanliness, free_1=free, public_1=public, accessible=accessible, buy_prod=buy_product, toiletries=toiletries, geom=coordinates, rating=rating, other_comment=other_comment)
        
        db.session.add(new_toilet)
        db.session.commit()

        # Pass the cookie variable of the user and latest id (with that cookie) from glasgow_toilets to votes table. 
        # This will ensure an entry in votes table coresponds to the entry in glasgow_toilets by matching their cookie and id  

        cookie_relation = session.query(Toilet.id) \
        .filter(Toilet.cookie_str == unique_str) \
        .order_by(Toilet.id.desc()) \
        .first()[0]

        new_vote = Votes(cookie_str=unique_str, id=cookie_relation)
        db.session.add(new_vote)
        db.session.commit()

        # Need to load points somewhere to reutn the last entry to the map after the POST request is executed
        #add_points()
        res.data = render_template('index.html', geojson_points=add_points())
        return res
    else:
        res.data = render_template('index.html', geojson_points=add_points())
        return res

@app.route('/votes', methods=['POST', 'GET'])
def upvote_toilet():
    if request.method == 'POST':

        cookie = request.cookies.get('unique-string')
        data_received = json.loads(request.data).get('postid')

        # Successfully received data from client. 

        # In the query below, check if the returned ID (ID of specific toilet) AND cookie string from current user both exist in a Votes table.
        # If entry exists, delete it from db, if not, insert row (ID as returned from client + current user's cookie string)
        
        add_vote = Votes(cookie_str=cookie, id=data_received)

        query = session.query(Votes.cookie_str, Votes.id) \
            .filter(Votes.cookie_str == cookie) \
            .filter(Votes.id == data_received) \
            .first() is not None
        #print(query)

        # Upvote functionality
        # When user clicks on like button, add row in votes table. If user already liked this specific feature, remove the row from table. 

        if query == False:
            db.session.add(add_vote)
            db.session.commit()
           
        elif query == True: 
            print("Entered True statement")
            
            delete = session.query(Votes) \
                .filter(Votes.cookie_str == cookie) \
                .filter(Votes.id == data_received) \
                .one()            
            
            local_session = db.session.merge(delete)  
            db.session.delete(local_session)
            db.session.commit()
        
        vote_count = session.query(Votes.id).filter(Votes.id == data_received).count()
        vote_dict = {'vote_nr' : vote_count}
        
        return jsonify(vote_dict)
    
    
@app.route('/delete-entry', methods=['POST'])
def delete_entry():
    
    post_id = json.loads(request.data).get('postid')
    print(post_id)

    delete_entry = session.query(Toilet) \
    .filter(Toilet.id == post_id) \
    .one()  
    
    local_session = db.session.merge(delete_entry)
    db.session.delete(local_session)
    db.session.commit()
    
    return str(post_id)
    

@app.route('/report-entry', methods=['POST'])
def report_entry():
    
    report_message = list(json.loads(request.data).values())[0]
    report_id = list(json.loads(request.data).values())[1]
    print(report_message + str(report_id))

    msg = Message('Glasgow Toilets report', sender='user@mailtrap.io', recipients= ['gregor.boltic@gmail.com'])
    msg.body = 'Reported id: ' + str(report_id) + '\nMessage: ' + report_message
    mail.send(msg)
    return jsonify('Your request has been successfully sent to the toilet admin. Thanks!')


if __name__ == "__main__":
    app.run(debug=True) 
