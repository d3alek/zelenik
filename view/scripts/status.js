function safariDateText(date_text) {
    return date_text.replace(/-/g,"/");
}

function dateFromUTCText(utc_text) {
    var wrong_date = new Date(safariDateText(utc_text));
    return new Date(wrong_date.getTime() - wrong_date.getTimezoneOffset() * 60000);
}

function fillStatus(enchanted, status_span, status_since_span) {
    status_class = 'error';
    status_text = 'грешка';
    status_since = 'неизвестно';

    if (enchanted['timestamp_utc']) {
        enchanted_utc = dateFromUTCText(enchanted['timestamp_utc']);
        enchanted_millis = enchanted_utc.getTime(); // enchanted utc time in millis
        now_millis = new Date().getTime(); // current utc time in millis 

        if (now_millis - enchanted_millis > 5000*60) {
            status_class = 'down';
            status_text = 'неизвестно';
            status_since = enchanted_utc.toLocaleString();
        }
        else {
            if (enchanted['state'] && enchanted['state']['boot_utc']) {
                status_class = 'up';
                status_text = 'живо';
                boot_utc = dateFromUTCText(enchanted['state']['boot_utc']); // Adding Z so that parse assumes UTC 
                status_since = boot_utc.toLocaleString();
            }
        }
    }

    status_span.setAttribute("class", status_class);
    status_span.innerText = status_text.substr(1);
    status_since_span.textContent = status_since;
}
