// src: https://www.sitepoint.com/javascript-this-event-handlers/
function AttachEvent(element, type, handler) {
    if (element.addEventListener) {
        element.addEventListener(type, handler, false);
    }
    else {
        element.attachEvent("on"+type, handler);
    }
}
