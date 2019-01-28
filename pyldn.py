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
                  'application/ld+json; profile="http://www.w3.org/ns/activitystreams', 'turtle', 'json-ld']

# Graph of the local inbox
ldp_url = URIRef("http://www.w3.org/ns/ldp#")
ldp = Namespace(ldp_url)

inbox_graph = Graph()

#IRI for ESIP Linked Data Notifications Inbox Graph
iri = 'http://cor.esipfed.org/ont/ldn/inbox'

if pyldnconf._storage == 'esip_cor':
    app.logger.info("Establishing swagger_client configuration for ESIP COR.")
    esip_cor = True
    # Configure HTTP basic authorization: basicAuth
    swagger_client.configuration.username = pyldnconf._cor_user
    swagger_client.configuration.password = pyldnconf._cor_pass
    # create an instance of the add_ont API
    # https://github.com/ESIPFed/corpy/blob/master/docs/OntologyApi.md#add_ont
    ont_instance = swagger_client.OntologyApi()
    # create an instance of the term_get API
    # https://github.com/ESIPFed/corpy/blob/master/docs/TermApi.md#term_get
    #term_instance = swagger_client.TermApi()

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
            try: 
                # Gets information about registered ontologies or terms
                api_response = ont_instance.ont_get(iri=iri, format='application/ld+json')
                print(api_response)
            except ApiException as e:
                print("Exception when calling OntologyApi->ont_get: %s\n" % e)
            resp = make_response(inbox_graph.serialize(format='application/ld+json'))
            resp.headers['Content-Type'] = 'application/ld+json'
        else:
            resp = make_response(inbox_graph.serialize(format='application/ld+json'))
            resp.headers['Content-Type'] = 'application/ld+json'
    elif request.headers['Accept'] in ACCEPTED_TYPES:
        if esip_cor:
            try: 
                # Gets information about registered ontologies or terms
                api_response = ont_instance.ont_get(iri='/ldn/', format=request.headers['Accept'])
                app.logger.info(api_response)
            except ApiException as e:
                app.logger.error("Exception when calling OntologyApi->ont_get: %s\n" % e)
            resp = make_response(inbox_graph.serialize(format=request.headers['Accept']))
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
    ldn_url = pyldnconf._inbox_url + "/" + ldn_uuid
    graphs[ldn_url] = g = Graph()
    try:
        g.parse(data=request.data, format=content_type[0])
    except: # Should not catch everything
        return 'Could not parse received {} payload'.format(content_type[0]), 500
    
    inbox_graph.add((URIRef(pyldnconf._inbox_url), ldp['contains'], URIRef(ldn_url)))
    app.logger.info('Created notification {}'.format(ldn_url))
    if esip_cor:
        #First update the Inbox graph with the new LDN IRI
        inbox_body = swagger_client.PutOnt()
        inbox_body.iri = iri.strip("/")
        inbox_body.name = 'ESIP Linked Data Notificaions Inbox Graph'
        inbox_body.visibility = 'public'
        inbox_body.status = 'testing'
        #body.metadata = ''
        inbox_body.org_name = pyldnconf._cor_org
        inbox_body.user_name = pyldnconf._cor_user
        inbox_body.uploaded_filename = 'inbox.ttl'
        inbox_body.contents = inbox_graph.serialize(format=request.headers['Content-Type']).decode("utf-8")
        inbox_body.format = request.headers['Content-Type']
        print(inbox_body)
        try:
            # Registers a brand new ontology
            ont_instance.update_ont(body=inbox_body)
        except ApiException as e:
            app.logger.error("Exception when calling OntologyApi->update_ont: %s\n" % e)

        #Then add the content of the new LDN.
        ldn_body = swagger_client.PostOnt()
        ldn_body.iri = iri + "/" + ldn_uuid
        ldn_body.original_iri = iri + "/" + ldn_uuid
        ldn_body.name = 'ESIP Linked Data Notification: ' + ldn_uuid
        ldn_body.org_name = pyldnconf._cor_org
        ldn_body.visibility = 'public'
        ldn_body.status = 'testing'
        ldn_body.user_name = pyldnconf._cor_user
        ldn_body.contents = request.data.decode("utf-8")
        ldn_body.format = request.headers['Content-Type']
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
    if pyldnconf._inbox_url + id not in graphs:
        return 'Requested notification does not exist', 404

    if 'Accept' not in request.headers or request.headers['Accept'] == '*/*' or 'text/html' in request.headers['Accept']:
        resp = make_response(graphs[pyldnconf._inbox_url + id].serialize(format='application/ld+json'))
        resp.headers['Content-Type'] = 'application/ld+json'
    elif request.headers['Accept'] in ACCEPTED_TYPES:
        resp = make_response(graphs[pyldnconf._inbox_url + id].serialize(format=request.headers['Accept']))
        resp.headers['Content-Type'] = request.headers['Accept']
    else:
        return 'Requested format unavailable', 415

    resp.headers['X-Powered-By'] = 'https://github.com/esipfed/pyldn'
    resp.headers['Allow'] = "GET"

    return resp

if __name__ == '__main__':
    logHandler = RotatingFileHandler('pyldn.log', maxBytes=1000, backupCount=1)
    logHandler.setLevel(logging.DEBUG)
    app.logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    logHandler.setFormatter(formatter)
    app.logger.addHandler(logHandler) 
    app.run(port=8088, debug=True)