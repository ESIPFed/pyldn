# pyldn
A python [Linked Data Notifications (LDN)](https://linkedresearch.org/ldn/) receiver.

**Original Author:**	Albert Meroño  
**Copyright:**	Albert Meroño, VU University Amsterdam  
**License:**	Apache 2 (see [license.txt](license.txt))

This 'cor' branch is a fork of that work which enables provision of an LDN service which
uses [ESIP's Community Ontology Reposotory](http://cor.esipfed.org) as the storage backend.

## Features
pyldn is a lightweight receiver for LDN. This means you can set up an inbox to receive notifications as Linked Data in seconds!

## Install
<pre>
git clone https://github.com/esipfed/pyldn
pip install -r requirements.txt
pip install git+https://github.com/ESIPFed/corpy.git
</pre>

## Configuration
Open `config.ini` and edit all values as appropriate. Note in order to use COR, you will need 
a COR account. You should also be part of the `ldn` Org. 

## Usage
<pre>
python pyldn.py
</pre>

Then, from a client you can discover an inbox

<pre>
curl -I -X GET http://cor.esipfed.org/ldn/

HTTP/1.0 200 OK
Content-Type: text/html; charset=utf-8
Content-Length: 3169
X-Powered-By: https://github.com/esipfed/pyldn
Link: <http://cor.esipfed.org/ont/ldn/inbox>; rel="http://www.w3.org/ns/ldp#inbox", <http://www.w3.org/ns/ldp#Resource>; rel="type", <http://www.w3.org/ns/ldp#RDFSource>; rel="type"
Server: Werkzeug/0.11.11 Python/3.6.5
Date: Thu, 31 Jan 2019 23:07:14 GMT
</pre>

You can request a list of the notification URLs it contains:

<pre>
curl -X GET -H'Accept: text/turtle' http://cor.esipfed.org/ldn/inbox/

HTTP/1.1 200 OK

@prefix ldp: &lt;http://www.w3.org/ns/ldp#&gt; .
@prefix rdf: &lt;http://www.w3.org/1999/02/22-rdf-syntax-ns#&gt; .
@prefix rdfs: &lt;http://www.w3.org/2000/01/rdf-schema#&gt; .
@prefix xml: &lt;http://www.w3.org/XML/1998/namespace&gt; .
@prefix xsd: &lt;http://www.w3.org/2001/XMLSchema#&gt; .

&lt;http://cor.esipfed.org/ldn/inbox&gt; a ldp:BasicContainer,
        ldp:Container,
        ldp:RDFSource,
        ldp:Resource ;
    ldp:contains &lt;http://cor.esipfed.org/ldn/inbox/1&gt;,
        &lt;http://cor.esipfed.org/ldn/inbox/2&gt; .
</pre>

You can even post new notifications to this inbox! You'll get the URL for your notification in the response headers:

<pre>
curl -i -X POST -d '&lt;foo&gt; &lt;bar&gt; &lt;foobar&gt; .' -H'Content-Type: text/turtle' http://cor.esipfed.org/ldn/inbox

HTTP/1.1 201 CREATED
Location: http://cor.esipfed.org/ldn/inbox/3
</pre>

If you want to retrieve the content of your brand new notification:

<pre>
curl -i -X GET -H'Accept: text/turtle' http://cor.esipfed.org/ldn/inbox/3

HTTP/1.1 200 OK

@prefix ns1: &lt;file:///home/amp/src/pyldn/&gt; .
@prefix rdf: &lt;http://www.w3.org/1999/02/22-rdf-syntax-ns#&gt; .
@prefix rdfs: &lt;http://www.w3.org/2000/01/rdf-schema#&gt; .
@prefix xml: &lt;http://www.w3.org/XML/1998/namespace&gt; .
@prefix xsd: &lt;http://www.w3.org/2001/XMLSchema#&gt; .

ns1:foo ns1:bar ns1:foobar .
</pre>

See the [latest LDN draft](https://linkedresearch.org/ldn/) for a complete and concise description of all you can do with LDN!
