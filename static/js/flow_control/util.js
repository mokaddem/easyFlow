function guid() {
    function s4() {
        return Math.floor((1 + Math.random()) * 0x10000)
          .toString(16)
          .substring(1);
    }
    return s4() + s4() + '-' + s4() + '-' + s4() + '-' +
    s4() + '-' + s4() + s4() + s4();
}

function objectToArray(obj) {
    return Object.keys(obj).map(function (key) {
        obj[key].id = key;
        return obj[key];
    });
}

function toggle_loading(display) {
    $('#loaderBack').toggleClass('loader-background', display);
    $('#loaderBack').toggle(display);
    $('#loader').toggle(display);
}

function execute_operation(operation, data) {
    $.ajax({
        type: "POST",
        url: url_project_operation,
        data: JSON.stringify(data),
        contentType: 'application/json; charset=utf-8',
        beforeSend: function() { toggle_loading(true); },
        complete: function() { toggle_loading(false); }
    });
    return false;
}
