from flask import render_template
from flask import request, url_for, g
from flaskexample import app
from sqlalchemy import create_engine
from sqlalchemy_utils import database_exists, create_database

import pandas as pd
import psycopg2
import re

user = 'cathy'
host = 'localhost'
dbname = 'doctordb'
db = create_engine('postgresql://%s%s/%s' % (user,host,dbname))
con = None
con = psycopg2.connect(database = dbname, user=user)

@app.route('/')
@app.route('/index')
def index():
    return render_template("input.html")

@app.route('/piechart')
def make_pie():
    return render_template("piechart.html")

@app.route('/about')
def about():
    return render_template("about.html")

@app.route('/base_layout')
def base_layout():
    return render_template("base_layout.html")


@app.route('/input')
def doctors_input():
    return render_template("input.html")


@app.route('/output')
def doctors_output():
    ## Pull 'first_name' and 'last_name' from input field and store it
    first_name = request.args.get('first_name')
    last_name = request.args.get('last_name')
    
    ## 2 (permitted) input cases:
    ## (1) User supplies both first and last
    ## (2) User supplies only last
    
    if first_name:
        ## Make uppercase for SQL search
        ## Check, only alpha characters allowed.
        first_name = first_name.upper().strip()
        if first_name:
            search_result = re.search(r'[A-Z]+', first_name)
            if search_result:
                first_name = re.search(r'[A-Z]+', first_name).group(0)

    last_name = last_name.upper().strip()
    if last_name:
        ## these checks check for invalid inputs like "1235"
        search_result = re.search(r'[A-Z]+', last_name)
        if search_result:
            last_name = re.search(r'[A-Z]+', last_name).group(0)
            print(last_name)

    query = ''
    query_results = []
    ## SELECT doctors from payments table by first and last, or just last_name
    if first_name and last_name:
        query = """
        SELECT DISTINCT npi
          ,nppes_provider_first_name AS first_name
          ,nppes_provider_last_org_name AS last_name
          ,nppes_provider_street1 AS street
          ,nppes_provider_city AS city
          ,nppes_provider_state AS state
          ,nppes_provider_zip AS zip_code
        FROM payments
        WHERE provider_type='Orthopedic Surgery'
        AND nppes_provider_first_name = '{0}'
        AND nppes_provider_last_org_name = '{1}'
        ORDER BY nppes_provider_state;
        """.format(first_name, last_name)
        
        query_results = pd.read_sql_query(query,con)
    elif last_name:
        query = """
        SELECT DISTINCT npi
          ,nppes_provider_first_name AS first_name
          ,nppes_provider_last_org_name AS last_name
          ,nppes_provider_street1 AS street
          ,nppes_provider_city AS city
          ,nppes_provider_state AS state
          ,nppes_provider_zip AS zip_code
        FROM payments
        WHERE provider_type='Orthopedic Surgery'
        AND nppes_provider_last_org_name = '{0}'
        ORDER BY nppes_provider_state;
        """.format(last_name)

        query_results = pd.read_sql_query(query,con)

    #print(query)
    #print(query_results)

    ## 3 possibilities:
    ## (1) Doctor does not exist in database
    ## (2) Multiple doctors with that name exist in database
    ## (3) A single doctor is found. => skip this case, make user select dr in output

    number_of_hits = len(query_results)
    
    if number_of_hits > 0:
        ## at least one doctor
        doctors = []
        for i in range(number_of_hits):
            adoctor = dict( first_name = query_results.loc[i,'first_name'],
                        last_name = query_results.loc[i,'last_name'],
                        street = query_results.loc[i,'street'],
                        city = query_results.loc[i,'city'],
                        state = query_results.loc[i,'state'],
                        zip_code = query_results.loc[i, 'zip_code'][:5],
                        npi = query_results.loc[i, 'npi'] )
            doctors.append(adoctor)

        return render_template("output.html",
                               doctors=doctors,
                               number_of_hits=number_of_hits)

    else:
        ## no doctors found
        return render_template("not_found.html",
                               first_name = first_name,
                               last_name = last_name,
                               by_doctor = 1)
    


@app.route('/view_doctor_profile/<npi>')
def view_profile(npi):
    ## Pull top 10 claims by the provider that are most relevant to
    ## the assigned topic/specialty

    query_name = """
    SELECT nppes_provider_first_name AS first_name
      ,nppes_provider_last_org_name AS last_name
    FROM summary
    WHERE npi = '{0}';
    """.format(npi)

    fullname = pd.read_sql_query(query_name,con)
    print(fullname)
    
    query = """
    SELECT hcpcs_code
      ,hcpcs_description
      ,place_of_service
      ,bene_unique_cnt
      ,topic
    FROM doctor_claims_for_topic
    WHERE npi = '{0}'
    ORDER BY rank ASC
    LIMIT 10;
    """.format(npi)

    print(query)
    query_results = pd.read_sql_query(query,con)
    print(query_results)

    topic = 'none'
    rows = []
    print('length of query results {0}'.format(len(query_results)))

    ##Create dictionary mapping topic numbers to labels
    topic_labels = ['spine/lower back',
                    'lower leg/ankle/foot',
                    'spine bones',
                    'blood, urinalysis tests',
                    'knee/pelvis/hip',
                    'hand/wrist/fingers',
                    'knee/shoulder',
                    'hospital',
                    'therapy',
                    'osteoarthritis']
    topic_dict = dict(enumerate(topic_labels))
    print(topic_dict)
    
    if len(query_results) > 0:
        topic_num = query_results.loc[0,'topic']
        topic = topic_dict[topic_num]
        print(topic)
        
        for i in range(len(query_results)):
            arow = dict(hcpcs_code = query_results.loc[i,'hcpcs_code'],
                        hcpcs_description = query_results.loc[i,'hcpcs_description'],
                        place_of_service = query_results.loc[i,'place_of_service'],
                        bene_unique_cnt = query_results.loc[i,'bene_unique_cnt'])
            rows.append(arow)
    try:
        print(rows)
        return render_template("view_doctor_profile.html",
                           rows=rows,
                           first_name=fullname.loc[0,'first_name'],
                           last_name=fullname.loc[0,'last_name'],
                           topic=topic,
                           npi=npi)
    except:
        return render_template('index.html')


@app.route('/by_specialty')
def by_specialty():
    ## Pull 'first_name' and 'last_name' from input field and store it
    topic = request.args.get('options')
    state = request.args.get('state')

    topic = int(topic)
    
    print(topic)
    print(state)

    if len(state) == 0:
        query = """
        SELECT npi
        ,nppes_provider_first_name AS first_name
        ,nppes_provider_last_org_name AS last_name
        ,probability
        ,nppes_provider_state AS state
        FROM topic_probability_per_npi
        WHERE topic={0}
        ORDER BY probability DESC
        LIMIT 10;
        """.format(topic)
    else:
        ## constrain by state
        query = """
        SELECT npi
        ,nppes_provider_first_name AS first_name
        ,nppes_provider_last_org_name AS last_name
        ,probability
        ,nppes_provider_state AS state
        FROM topic_probability_per_npi
        WHERE topic={0}
        AND nppes_provider_state='{1}'
        ORDER BY probability DESC
        LIMIT 10;
        """.format(topic, state)

    print(query)
    query_results = pd.read_sql_query(query,con)
    print(query_results)

    number_of_hits = len(query_results)

    ##Create dictionary mapping topic numbers to labels
    topic_labels = ['spine/lower back',
                    'lower leg/ankle/foot',
                    'spine bones',
                    'blood, urinalysis tests',
                    'knee/pelvis/hip',
                    'hand/wrist/fingers',
                    'knee/shoulder',
                    'hospital',
                    'therapy',
                    'osteoarthritis']
    topic_dict = dict(enumerate(topic_labels))
    topic = topic_dict[topic]
    ## 2 possibilities:
    ## (1) > 0 hits
    ## (2) 0 hits
    
    if number_of_hits > 0:
         ## at least 1 doctor
         doctors = []
         for i in range(number_of_hits):
             adoctor = (dict( first_name = query_results.loc[i,'first_name'],
                              last_name = query_results.loc[i,'last_name'],
                              probability = round(query_results.loc[i,'probability'],3),
                              state = query_results.loc[i, 'state'],
                              npi = query_results.loc[i, 'npi']))
             doctors.append(adoctor)

         return render_template("output_specialty.html",
                                doctors=doctors,
                                topic=topic,
                                state=state)
    else:
        return render_template("not_found.html",
                               topic=topic,
                               state=state,
                               by_specialty = 1)
