#!/usr/bin/env python

# pyldn: A python Linked Data Notifications (LDN) receiver

from flask import Flask, request, render_template, make_response
from logging.handlers import RotatingFileHandler
from rdflib import Graph, URIRef, RDF, Namespace
from swagger_client.rest import ApiException

import logging
import requests
import swagger_client
import uuid

# pyldn modules
from pyldnconfig import Pyldnconfig

# The Flask app
app = Flask(__name__)

# Config
pyldnconf = Pyldnconfig()
app.logger.info(pyldnconf.log_config())

#Default to not using 'esip_cor' storage config
esip_cor = False

# Accepted content types
ACCEPTED_TYPES = ['application/ld+json',
                  'text/turtle',
                  'application/ld+json; profile="http://www.w3.org/ns/activitystreams', 
                  'turtle', 
                  'json-ld']

# Graph of the local inbox
ldp_url = URIRef("http://www.w3.org/ns/ldp#")
ldp = Namespace(ldp_url)

inbox_graph = Graph()

#IRI for ESIP Linked Data Notifications Inbox Graph
iri = 'http://cor.esipfed.org/ont/ldn/inbox'

if pyldnconf._storage == 'esip_cor':
    app.logger.info("Establishing swagger_client configuration for ESIP COR.")
    esip_cor = True
    configuration = swagger_client.Configuration()
    configuration.username = pyldnconf._cor_user
    configuration.password = pyldnconf._cor_pass
    api_client = swagger_client.ApiClient(configuration)
    ont_instance = swagger_client.OntologyApi(api_client)

inbox_graph.add((URIRef(pyldnconf._inbox_url), RDF.type, ldp['Resource']))
inbox_graph.add((URIRef(pyldnconf._inbox_url), RDF.type, ldp['RDFSource']))
inbox_graph.add((URIRef(pyldnconf._inbox_url), RDF.type, ldp['Container']))
inbox_graph.add((URIRef(pyldnconf._inbox_url), RDF.type, ldp['BasicContainer']))
inbox_graph.bind('ldp', ldp)

# Dict for the notification graphs
# keys = graph names, values = rdflib.Graph()
graphs = {}

# Server routes
@app.route('/', methods=['GET', 'POST'])
def pyldn():
    resp = make_response(render_template('index.html'))
    resp.headers['X-Powered-By'] = 'https://github.com/esipfed/pyldn'
    resp.headers['Link'] =  '<' + pyldnconf._inbox_url + '>; rel="http://www.w3.org/ns/ldp#inbox", <http://www.w3.org/ns/ldp#Resource>; rel="type", <http://www.w3.org/ns/ldp#RDFSource>; rel="type"'

    return resp

@app.route(pyldnconf._inbox_path, methods=['HEAD', 'OPTIONS'])
def head_inbox():
    resp = make_response()
    resp.headers['X-Powered-By'] = 'https://github.com/esipfed/pyldn'
    resp.headers['Allow'] = "GET, HEAD, OPTIONS, POST"
    resp.headers['Link'] = '<http://www.w3.org/ns/ldp#Resource>; rel="type", <http://www.w3.org/ns/ldp#RDFSource>; rel="type", <http://www.w3.org/ns/ldp#Container>; rel="type", <http://www.w3.org/ns/ldp#BasicContainer>; rel="type"'
    resp.headers['Accept-Post'] = 'application/ld+json, text/turtle'

    return resp

@app.route(pyldnconf._inbox_path, methods=['GET'])
def get_inbox():
    app.logger.info("Requested inbox data of {} in {}".format(request.url, request.headers['Accept']))
    if not request.headers['Accept'] or request.headers['Accept'] == '*/*' or 'text/html' in request.headers['Accept']:
        if esip_cor:
            format = get_simple_format(content_type[0])

            # Get existing LDN Inbox Graph from COR
            api_call = ("http://cor.esipfed.org/ont/api/v0/ont?format=%s&iri=%s" % ('ttl', iri))
            existing_graph = Graph()
            existing_graph.parse(api_call)
            resp = make_response(existing_graph.serialize(format='application/ld+json'))
            resp.headers['Content-Type'] = 'application/ld+json'
        else:
            resp = make_response(inbox_graph.serialize(format='application/ld+json'))
            resp.headers['Content-Type'] = 'application/ld+json'
    elif request.headers['Accept'] in ACCEPTED_TYPES:
        if esip_cor:
            api_call = ("http://cor.esipfed.org/ont/api/v0/ont?format=%s&iri=%s" % ('ttl', iri))
            existing_graph = Graph()
            existing_graph.parse(api_call)
            resp = make_response(existing_graph.serialize(format=request.headers['Accept']))
            resp.headers['Content-Type'] = request.headers['Accept']
        else:
            resp = make_response(inbox_graph.serialize(format=request.headers['Accept']))
            resp.headers['Content-Type'] = request.headers['Accept']
    else:
        return 'Requested format unavailable', 415

    resp.headers['X-Powered-By'] = 'https://github.com/esipfed/pyldn'
    resp.headers['Allow'] = "GET, HEAD, OPTIONS, POST"
    resp.headers['Link'] = '<http://www.w3.org/ns/ldp#Resource>; rel="type", <http://www.w3.org/ns/ldp#RDFSource>; rel="type", <http://www.w3.org/ns/ldp#Container>; rel="type", <http://www.w3.org/ns/ldp#BasicContainer>; rel="type"'
    resp.headers['Accept-Post'] = 'application/ld+json, text/turtle'

    return resp

@app.route(pyldnconf._inbox_path, methods=['POST'])
def post_inbox():
    app.logger.info("Received request to create notification")
    app.logger.info("Headers: {}".format(request.headers))
    # Check if there's acceptable content
    content_type = [s for s in ACCEPTED_TYPES if s in request.headers['Content-Type']]
    app.logger.info("Interpreting content type as {}".format(content_type))
    if not content_type:
        return 'Content type not accepted', 500
    if not request.data:
        return 'Received empty payload', 500

    resp = make_response()

    ldn_uuid = uuid.uuid4().hex 
    ldn_url = iri + "/" + ldn_uuid
    graphs[ldn_url] = g = Graph()
    try:
        g.parse(data=request.data, format=content_type[0])
    except: # Should not catch everything
        return 'Could not parse received {} payload'.format(content_type[0]), 500
    
    inbox_graph.add((URIRef(pyldnconf._inbox_url), ldp['contains'], URIRef(ldn_url)))
    app.logger.info('Created notification {}'.format(ldn_url))
    if esip_cor:
        #First update the Inbox graph with the new LDN IRI. This involves three steps.
        # 1. Get existing LDN Inbox Graph from COR,
        # 2. Merge new LDN into existing graph and PUT
        # 3. POST the new LDN separately to COR

        format = get_simple_format(content_type[0])

        # 1. Get existing LDN Inbox Graph from COR
        api_call = ("http://cor.esipfed.org/ont/api/v0/ont?format=%s&iri=%s" % ('ttl', iri))
        existing_graph = Graph()
        existing_graph.parse(api_call)

        # 2. Merge new LDN into existing graph and PUT        
        merged_graph = existing_graph + inbox_graph

        inbox_body = swagger_client.PutOnt()
        inbox_body.iri = iri.strip("/")
        inbox_body.name = 'ESIP Linked Data Notifications Inbox Graph'
        inbox_body.visibility = 'public'
        inbox_body.status = 'stable'
        inbox_body.uploaded_filename = 'inbox.ttl'
        inbox_body.contents = merged_graph.serialize(format=content_type[0]).decode("utf-8")
        inbox_body.format = format
        inbox_body.user_name = pyldnconf._cor_user
        try:
            ont_instance.update_ont(body=inbox_body)
        except ApiException as e:
            app.logger.error("Exception when calling OntologyApi->update_ont: %s\n" % e)

        # 3. POST the new LDN separately to COR
        ldn_body = swagger_client.PostOnt()
        ldn_body.iri = iri + "/" + ldn_uuid
        ldn_body.original_iri = iri + "/" + ldn_uuid
        ldn_body.name = 'ESIP Linked Data Notification: ' + ldn_uuid
        ldn_body.org_name = pyldnconf._cor_org
        ldn_body.visibility = 'public'
        ldn_body.status = 'stable'
        ldn_body.user_name = pyldnconf._cor_user
        ldn_body.contents = request.data.decode("utf-8")
        ldn_body.format = format
        try: 
            # Registers a brand new ontology
            ont_instance.add_ont(ldn_body)
        except ApiException as e:
            app.logger.error("Exception when calling OntologyApi->add_ont: %s\n" % e)

    resp.headers['Location'] = ldn_url

    return resp, 201

@app.route(pyldnconf._inbox_path + '<id>', methods=['GET'])
def get_notification(id):
    app.logger.info("Requested notification data of {}".format(request.url))
    app.logger.info("Headers: {}".format(request.headers))

    # Check if the named graph exists
    app.logger.info("Dict key is {}".format(pyldnconf._inbox_url + id))
    if esip_cor:
        # 1. Get existing LDN from COR
        ldn = iri + "/" + id
        print(ldn)
        try:
            api_call = ("http://cor.esipfed.org/ont/api/v0/ont?format=%s&iri=%s" % ('ttl', ldn))
        except Excepttion as e:
            app.logger.error('Exception retrieving notification %s from ESIP Linked Data Notifications Inbox Graph. Named graph absent!' % ldn)
            return 'Requested notification does not exist', 404
        if api_call is not None:
            named_graph = Graph()
            named_graph.parse(api_call)            
    else:
        if pyldnconf._inbox_url + id not in graphs:
            return 'Requested notification does not exist', 404

    if 'Accept' not in request.headers or request.headers['Accept'] == '*/*' or 'text/html' in request.headers['Accept']:
        if esip_cor:
            resp = make_response(named_graph.serialize(format='application/ld+json'))
            resp.headers['Content-Type'] = 'application/ld+json'
        else:
            resp = make_response(graphs[pyldnconf._inbox_url + id].serialize(format='application/ld+json'))
            resp.headers['Content-Type'] = 'application/ld+json'
    elif request.headers['Accept'] in ACCEPTED_TYPES:
        if esip_cor:
            resp = make_response(named_graph.serialize(format=request.headers['Accept']))
            resp.headers['Content-Type'] = request.headers['Accept']
        else:
            resp = make_response(graphs[pyldnconf._inbox_url + id].serialize(format=request.headers['Accept']))
            resp.headers['Content-Type'] = request.headers['Accept']
    else:
        return 'Requested format unavailable', 415

    resp.headers['X-Powered-By'] = 'https://github.com/esipfed/pyldn'
    resp.headers['Allow'] = "GET"

    return resp

def get_simple_format(mime):
    if mime == 'application/ld+json' or 'application/ld+json; profile="http://www.w3.org/ns/activitystreams' or 'json-ld':
        mime = 'jsonld'
    elif mime == 'text/turtle' or 'turtle':
        mime == 'ttl'

    return mime

if __name__ == '__main__':
    logHandler = RotatingFileHandler('pyldn.log', maxBytes=1000, backupCount=1)
    logHandler.setLevel(logging.DEBUG)
    app.logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    logHandler.setFormatter(formatter)
    app.logger.addHandler(logHandler) 
    app.run(port=8088, debug=True)