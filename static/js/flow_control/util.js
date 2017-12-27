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

function toggle_btn_pipe(display) {
    var btnPipe = $('button[name="pipe"]');
    btnPipe.toggleClass('btn-default', !display);
    btnPipe.toggleClass('btn-primary', display);
}

// merge fields of obj2 into obj1
function mergeInto(obj1, obj2) {
    for (var key in obj2) {
        if (obj2.hasOwnProperty(key)) {
            obj1[key] = obj2[key];
        }
    }
    return obj1;
}
