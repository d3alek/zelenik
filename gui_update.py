import json

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

def error(method, message):
    print("! gui_update/%s: %s" % (method, message))

def update_plot_background(db, a_thing, svg_bytes):
    content_type = 'text/html'
    thing = db.resolve_thing(a_thing)

    db.update_plot_background(thing, svg_bytes)

    if thing == a_thing:
        back_url = ('/db/' + thing)
    else:
        back_url = ('/na/' + a_thing)

    return content_type, HTML % REDIRECT % (back_url, 'Успешно.', back_url)

def update_db(db, a_thing, state, value):
    thing = db.resolve_thing(a_thing)

    if state == "thing-alias":
        db.update_thing_alias(thing, value)
        a_thing = value
    else:
        try:
            value_dict = json.loads(value)
        except ValueError:
            error("handle_update", "Could not parse json value. %s %s %s" % (a_thing, state, value))
            return 'Could not parse json value %s %s %s' % (state, a_thing, value)

        if state == 'desired': 
            db.update_desired(thing, value_dict)
        elif state == 'displayables':
            db.update_displayables(thing, value_dict)
        else:
            error("update_db", "Not allowed to change state. %s %s %s" % (thing, state, value_dict))
            return 'Not allowed to change state. %s %s %s' % (thing, state, value_dict)

    if thing == a_thing:
        back_url = ('/db/' + thing)
    else:
        back_url = ('/na/' + a_thing)
    return REDIRECT % (back_url, 'Успешно.', back_url)

def handle_update(db, thing, state, value):
    content_type = 'text/html'

    text = update_db(db, thing, state, value)

    return content_type, HTML % text
