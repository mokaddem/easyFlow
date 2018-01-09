function objectToArray(obj) {
    return Object.keys(obj).map(function (key) {
        obj[key].id = key;
        return obj[key];
    });
}

function getCookie(name) {
    var value = "; " + document.cookie;
    var parts = value.split("; " + name + "=");
    if (parts.length == 2) {
        var ret = parts.pop().split(";").shift();
        ret = ret.replace(/\"/g ,''); // remove " from cookie
        return ret;
    }
}

function toggle_loading(display, quick) {
    if(quick && display) {
        $.notify({
                icon: 'glyphicon glyphicon-save',
                title: '<strong>Saving... </strong>',
                message: "",
            },{
                type: 'info',
                allow_dismiss: false,
                showProgressbar: true,
                delay: 500,
                // timer: 1000,
                placement: {
                    from: "top",
                    align: "right"
                },
                z_index: 3000,
                animate: {
                    enter: 'animated bounceInDownFast',
                    exit: 'animated flipOutXFast'
                }
        });
    } else {
        $('#loaderBack').toggleClass('loader-background', display);
        $('#loaderBack').toggle(display);
        $('#loader').toggle(display);
    }
}

function notify(title, message, type) {
    $.notify({
    // options
    icon: 'glyphicon glyphicon-warning-sign',
    title: '<strong>'+title+'</strong>',
    message: message,
    // target: '_blank'
},{
    // settings
    // element: 'body',
    // position: null,
    type: type,
    // allow_dismiss: true,
    // newest_on_top: false,
    // showProgressbar: false,
    placement: {
        from: "top",
        align: "right"
    },
    // offset: 20,
    // spacing: 10,
    z_index: 3000,
    // delay: 5000,
    // timer: 1000,
    // url_target: '_blank',
    // mouse_over: null,
    animate: {
        enter: 'animated bounceInDown',
        exit: 'animated flipOutX'
    },
    // onShow: null,
    // onShown: null,
    // onClose: null,
    // onClosed: null,
    // icon_type: 'class',
    // template: '<div data-notify="container" class="col-xs-11 col-sm-3 alert alert-{0}" role="alert">' +
    //     '<button type="button" aria-hidden="true" class="close" data-notify="dismiss">×</button>' +
    //     '<span data-notify="icon"></span> ' +
    //     '<span data-notify="title">{1}</span> ' +
    //     '<span data-notify="message">{2}</span>' +
    //     '<div class="progress" data-notify="progressbar">' +
    //     	'<div class="progress-bar progress-bar-{0}" role="progressbar" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100" style="width: 0%;"></div>' +
    //     '</div>' +
    //     '<a href="{3}" target="{4}" data-notify="url"></a>' +
    // '</div>'
});
}

function toggle_btn_pipe(display) {
    var btnPipe = $('button[name="pipe"]');
    btnPipe.toggleClass('btn-default', !display);
    btnPipe.toggleClass('btn-primary', display);
}

// merge fields of obj2 into obj1
function mergeInto(obj1, obj2) {
    var to_ret = $.extend( {}, obj1, obj2 );
    return to_ret;
}

// function validateForm(btn) {
function validateForm(formID) {
    var form = document.getElementById(formID);
    var res = form.checkValidity();
    if (res) { // form is valid
        return res;
    } else {
        notify('Invalid form:', "One or more fields are not valid", "danger");
        return res;
    }
}

function getFormData(formID) {
    return $('#'+formID).serializeArray().reduce(function(obj, item) {
        var itemValue = !isNaN(parseFloat(item.value)) && isFinite(item.value) ? parseFloat(item.value) : item.value;
        obj[item.name] = itemValue;
        return obj;
    }, {});
}

function create_html_from_json(pName, j) {
    var div = document.createElement('div');
    div.classList.add('form-group')

    var domType = j.DOM
    var label = document.createElement('label');
    label.innerHTML = j.label;
    var elem = document.createElement(domType);
    elem.setAttribute("required", "");
    elem.setAttribute("name", pName);
    elem.classList.add('form-control');

    switch (domType) {
        case "input": // should support text, password, checkbox, email, number, range, tel, url
            elem.setAttribute("placeholder", j.placeholder);
            elem.setAttribute("type", j.inputType);
            elem.setAttribute("min", j.min);
            elem.setAttribute("max", j.max);
            elem.setAttribute("step", j.step);
            elem.setAttribute("value", j.default);
            break;
        case "select":
            for (var option of j.options) {
                var domOption = document.createElement('option');
                domOption.innerHTML = option;
                if (option == j.default) {
                    domOption.setAttribute("required", "");
                }
                elem.appendChild(domOption);
            }
            break;
        default:
            break;
    }
    div.appendChild(label);
    div.appendChild(elem);
    return div;
}

function add_html_based_on_json(pName, jqObject) {
    var config = custom_config_json[pName];
    for (var pName in config) {
        if (config.hasOwnProperty(pName)) {
            var domElement = create_html_from_json(pName, config[pName])
            jqObject.append(domElement)
        }
    }
}
