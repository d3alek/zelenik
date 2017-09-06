import json
from logger import Logger
logger = Logger("gui_update")

HTML = '<!DOCTYPE html> \
<html> \
    <head> \
        <meta charset="utf-8"> \
        <meta name="viewport" content="width=device-width" /> \
        <title>Зеленик</title> \
    </head> \
    <body>%s</body> \
</html>'

REDIRECT = '<meta http-equiv="refresh" content="0; url=%s" /> %s <a href="%s"> Назад </a> '

def update_plot_background(db, a_thing, svg_bytes):
    content_type = 'text/html'
    thing = db.resolve_thing(a_thing)

    db.update('plot-background', thing, svg_bytes)

    if thing == a_thing:
        back_url = ('/db/' + thing)
    else:
        back_url = ('/na/' + a_thing)

    return content_type, HTML % REDIRECT % (back_url, 'Успешно.', back_url)

def update_db(db, a_thing, state, value, ret):
    log = logger.of('update_db')
    thing = db.resolve_thing(a_thing)

    if state == "thing-alias":
        db.update('thing-alias', thing, value)
        a_thing = value
    else:
        try:
            value_dict = json.loads(value)
        except ValueError:
            log.error("Could not parse json value. %s %s %s" % (a_thing, state, value))
            return 'Could not parse json value %s %s %s' % (state, a_thing, value)

        if thing == None:
            log.warning('First time heard of thing %s\nAssuming it is a new thing' % a_thing)
            thing = a_thing
        db.update(state, thing, value_dict)

    if ret:
        back_url = ret
    elif thing == a_thing:
        back_url = ('/db/' + thing)
    else:
        back_url = ('/na/' + a_thing)
    return REDIRECT % (back_url, 'Успешно.', back_url)

def handle_update(db, thing, state, value, ret):
    content_type = 'text/html'

    text = update_db(db, thing, state, value, ret)

    return content_type, HTML % text
