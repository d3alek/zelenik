import json

REDIRECT = '<meta http-equiv="refresh" content="0; url=%s" /> %s <a href="%s"> Go back. </a> '

def handle_update(db, thing, state, value):
    content_type = 'text/html'

    try:
        value_dict = json.loads(value)
    except ValueError:
        error("handle_update", "Could not parse json value. %s %s %s" % (thing, state, value))
        return content_type, ('Could not parse json value %s. %s %s' % (state, thing, value)).encode('utf-8')
    
    if state == 'desired': 
        db.update_desired(thing, value_dict)
    elif state == 'aliases':
        db.update_aliases(thing, value_dict)
    else:
        return content_type, ('Not allowed to change state %s. %s %s' % (state, thing, value)).encode('utf-8')

    back_url = ('/db/' + thing)
    return content_type, (REDIRECT % (back_url, 'Success.', back_url)).encode('utf-8')
