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

function format_proc_data(moduleName, puuid, moduleType, bytes, flowItem, time, cpu_load, memory_load, pid, state, message) {
    var bytes_formated_in = bytes.bytes_in > 0 ? String((parseFloat(bytes.bytes_in)/1048576.0).toFixed(2)) : String(0);
    var bytes_formated_out = bytes.bytes_out > 0 ? String((parseFloat(bytes.bytes_out)/1048576.0).toFixed(2)) : String(0);
    var bytes_formated = bytes_formated_in + ' / ' + bytes_formated_out + ' MB';

    var flowItem_formated_in = flowItem.flowItem_in > 0 ? String(flowItem.flowItem_in) : String(0);
    var flowItem_formated_out = flowItem.flowItem_out > 0 ? String(flowItem.flowItem_out) : String(0);
    var flowItem_formated = flowItem_formated_in + ' / ' + flowItem_formated_out + ' FlowItems';
    var memory_load_formated = (memory_load > 0 ? String((parseFloat(memory_load)/1048576.0).toFixed(2)) : String(0)) + ' MB';

    cpu_load = cpu_load>0 ? cpu_load : 0;
    time = time!='?' ? time : 0;
    var formatted = {
        moduleName:   moduleName,
        type:         moduleType,
        uuid:         puuid,
        bytes:        bytes_formated,
        flowItems:     flowItem_formated,
        time:         String(parseFloat(time).toFixed(2))+'sec',
        cpuload:      cpu_load+'%',
        memload:      memory_load_formated,
        pid:          pid,
        state:        state,
        customMessage:message
    };
    return formatted;
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

function getModalTypeFromProcessType(processType) {
    switch(processType){
        case 'multiplexer_in':
            return 'AddMultInput';
        case 'multiplexer_out':
            return 'AddMultOutput';
        case 'switch':
            return 'AddSwitch';
        default:
            return 'AddProcess';
    }
}

// function validateForm(btn) {
function validateForm(formID) {
    var form = document.getElementById(formID);
    var res = form.checkValidity();
    if (res) { // form is valid
        return res;
    } else {
        var err_fields = [];
        for (i = 0; i < form.length ;i++) {
            if(!form.elements[i].checkValidity()) {
                err_fields.push(form.elements[i].getAttribute('name'));
            }
        }
        notify('Invalid form:', "One or more fields are not valid: "+err_fields, "danger");
        return res;
    }
}

function getFormData(formID) {
    // enable all fields so that they get picked by serializeArray
    var disabled = $('#'+formID).find(':input:disabled').removeAttr('disabled');
    var formData = $('#'+formID).serializeArray().reduce(function(obj, item) {
        var itemValue = !isNaN(parseFloat(item.value)) && isFinite(item.value) ? parseFloat(item.value) : item.value;
        obj[item.name] = itemValue;
        return obj;
    }, {});
    /* Because serializeArray() ignores checkboxes and radio buttons: */
    jQuery('#'+formID+' input[type=checkbox]').map(
                    function() {
                        formData[this.name] = this.checked;
                    }).get();
    // disable previously disabled fields
    disabled.attr('disabled','disabled');
    return formData
}

function fillForm(formID, formIDCustom, isUpdate, formData) {
    for(key in formData) {
        if(formData.hasOwnProperty(key)){
            // standard input
            var imp = $('#'+formID).find('input[name='+key+']');
            imp.val(formData[key]);

            // select
            var sel = $('#'+formID).find('select[name='+key+']');
            sel.val(formData[key]);
            // disable changing the process type
            if (key == 'type') {
                // sel.prop('disabled', true);
            }
        }
    }

    // empty form and create input for custom config
    $('#'+formIDCustom).empty();
    var selected_type = $('#'+formID).find('[name="type"]').val()
    if (formID == "formAddSwitch") {
        add_html_based_on_json(selected_type, $('#'+formIDCustom), isUpdate, formData.connections);
    } else {
        add_html_based_on_json(selected_type, $('#'+formIDCustom), isUpdate, undefined);
    }
    // add data for custom config
    var form_custom_config = formData.custom_config;
    for(key in form_custom_config) {
        if(form_custom_config.hasOwnProperty(key)){
            // standard input
            var imp = $('#'+formIDCustom).find('input[name='+key+']')
            imp.val(form_custom_config[key]);
            if (imp.attr('type') == 'checkbox') {
                imp.prop( "checked", form_custom_config[key] );
            }
            // select
            $('#'+formIDCustom).find('select[name='+key+']').val(form_custom_config[key]);

            // open tab if needed
            try { // may happen on input content
                $('#'+key+'_additional_options_'+form_custom_config[key]).collapse('toggle');
            } catch (e) {}
        }
    }

}

function create_html_from_json(pName, j, isUpdate) {
    var div = document.createElement('div');
    div.classList.add('form-group')

    var domType = j.DOM
    var label = document.createElement('label');
    label.innerHTML = j.label;
    var elem = document.createElement(domType);
    // if (j.required == 'true') {
    if (j.required) {
        elem.setAttribute("required", "");
    }
    if (isUpdate && (j.dynamic_change === undefined || j.dynamic_change == false)) {
        elem.setAttribute("disabled", "");
    }
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
            if (j.inputType == "checkbox") {
                elem.setAttribute('checked', j.default);
            }
            break;
        case "select":
            for (var option of j.options) {
                var domOption = document.createElement('option');
                domOption.innerHTML = option;
                domOption.value = option;
                if (option == j.default) {
                    domOption.setAttribute("selected", "");
                }
                elem.appendChild(domOption);
            }
            break;
        default:
            break;
    }
    // create collapsible pannel for SELECT options
    var divPG = document.createElement('div');
    divPG.classList.add('panel-group');
    divPG.setAttribute("id", pName+'_panelGroup');
    var divPan = document.createElement('div');
    divPan.classList.add('panel', 'panel-default', 'border-no-top');
    if (typeof(j.additional_options) !== undefined) {
        // iterate over each possible option and create a dedicated pannel.
        for (var option in j.additional_options) {
            if (j.additional_options.hasOwnProperty(option)) {
                var divHead = document.createElement('div');
                divHead.classList.add('panel-heading');
                var head4 = document.createElement('h4');
                head4.classList.add('panel-title');
                head4.innerHTML = option;
                divHead.appendChild(head4)
                var divCollapse = document.createElement('div');
                divCollapse.classList.add('panel-collapse', 'collapse');
                divCollapse.setAttribute("id", pName+'_additional_options_'+option);
                var divBody = document.createElement('div');
                divBody.classList.add('panel-body');

                // recursive call to generate html
                for (var fName in j.additional_options[option]) {
                    if (j.additional_options[option].hasOwnProperty(fName)) {
                        var domElement = create_html_from_json(pName+'_'+fName, j.additional_options[option][fName], isUpdate)
                        divBody.appendChild(domElement)
                    }
                }
                // append all element to form the collapsible panel
                divCollapse.appendChild(divBody)
                divPan.appendChild(divCollapse)
                divPG.appendChild(divPan)
            }
        }
        // add the listener to display the panel
        elem.addEventListener("change", function() {
            selected = this.value;
            if (this.type == "checkbox") { // value is not correct if it is a checkbox
                selected = this.checked;
            }
            // close active pannel
            var actives = $('#'+pName+'_panelGroup').find('.in, .collapsing');
            actives.each( function (index, element) {
                $(element).collapse('hide');
            });

            try{ // may happen on input content
                $('#'+pName+'_additional_options_'+selected).collapse('toggle');
            } catch (e) {}

        });
    }

    div.appendChild(label);
    div.appendChild(elem);
    div.appendChild(divPG);
    return div;
}

function add_html_based_on_json(pName, jqObject, isUpdate, jsonProvided) {
    var config = jsonProvided === undefined ? custom_config_json[pName] : jsonProvided;
    for (var pName in config) {
        if (config.hasOwnProperty(pName)) {
            var domElement = create_html_from_json(pName, config[pName], isUpdate)
            jqObject.append(domElement)
        }
    }
}

function create_json_for_switch(connectedNodesName) {
    var j = {};
    var numberOfChannel = [];
    for (var i=1; i<connectedNodesName.length+1; i++) { numberOfChannel.push(String(i)); }
    for (var buff of connectedNodesName) {
        j[buff.uuid] = {
            "label": buff.name + " channel:",
            "DOM": "select",
            "options": numberOfChannel,
            "default": "1",
            "required": false,
            "dynamic_change": true
        };
    }
    return j;
}

function get_node_size_from_type(type) {
    switch (type) {
        case "process":
            return 75;
        case "multiplexer_in":
            return 50;
        case "multiplexer_out":
            return 50;
        case "remote_input":
            return 50;
        case "remote_output":
            return 50;
        case "switch":
            return 50;
        case "buffer":
            return 30;
        default:
            // default should be a process type
            return 75;

    }
}

function sparklineNumberFormatter(number) {
    var d = new Date(number*1000);
    var now = new Date().getTime()/1000;
    if (now-buffer_time_spanned_in_min*60 <= number && number <= now) {
        var ret = d.toTimeString();
        var i = ret.indexOf(' ');
        return ret.slice(0, i);
    } else {
        return number;
    }
}
