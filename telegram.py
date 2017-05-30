import json
import urllib.request

LONG_POLL_DURATION = 120
API_BASE = 'https://api.telegram.org/bot'

class NonJsonResponseException(Exception):
	def __init__(self, contentType):
		message = "Received response with content type '%s'. This sometimes happens if you use an invalid token." % (contentType,)
		super().__init__(message)

def makeRequest(token, func, params):
	url = API_BASE + token + '/' + func
	paramsJson = json.dumps(params)

	req = urllib.request.Request(url, paramsJson.encode('utf-8'))
	req.add_header('Content-Type', 'application/json')

	resp = urllib.request.urlopen(req)
	respContentType = resp.info().get_content_type()
	if respContentType != 'application/json':
		raise NonJsonResponseException(respContentType)

	return json.loads(resp.read().decode('utf-8'))

def getOneUpdate(token, lastUpdateId=0):
	while True:
		updates = makeRequest(token, 'getUpdates', { 'limit': 1, 'offset': lastUpdateId, 'timeout': LONG_POLL_DURATION })
		results = updates['result']
		if len(results) == 1:
			result = results[0]
			return result
