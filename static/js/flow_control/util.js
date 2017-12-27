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
    data.operation = operation;
    $.ajax({
        type: "POST",
        url: url_project_operation,
        data: JSON.stringify(data),
        contentType: 'application/json; charset=utf-8',
        beforeSend: function() { toggle_loading(true); },
        complete: function() { toggle_loading(false); }
    });
    list_projects();
}

function send_file(formID, url) {
    var form = $('#'+formID)[0];
    var formData = new FormData(form);
    $.ajax({
      url: url,
      type: 'POST',
      processData: false, // important
      contentType: false, // important
      data: formData,
      beforeSend: function() { toggle_loading(true); },
      complete: function() { toggle_loading(false); }
    });
    list_projects();
}
