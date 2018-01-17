function save_network() {
    var nodes = network.getPositions();
    nodes = objectToArray(nodes);
    nodes.forEach(function(node) {
        node.connections = network.getConnectedNodes(node.id, 'to');
    });
    $.ajax({
        url: url_save_network,
        type: 'POST',
        data: JSON.stringify(nodes),
        contentType: 'application/json; charset=utf-8',
        success: function(msg) {
            console.log("Flow saved");
        },
        failure: function(msg, textStatus) {
            alert("An error occured, flow not saved");
            console.log(msg, textStatus);
        }
    });
}

function execute_operation(operation, data) {
    data.operation = operation;
    $.ajax({
        type: "POST",
        url: url_project_operation,
        data: JSON.stringify(data),
        contentType: 'application/json; charset=utf-8',
        beforeSend: function() { toggle_loading(true); },
        complete: function() { toggle_loading(false); list_projects(); }
    });
}

function send_file(formID, url, callback) {
    var form = $('#'+formID)[0];
    var formData = new FormData(form);
    $.ajax({
        url: url,
        type: 'POST',
        processData: false, // important
        contentType: false, // important
        data: formData,
        beforeSend: function() { toggle_loading(true); },
        complete: function(response) {
            toggle_loading(false);
            callback(response.responseJSON);
        }
    });
}

function load_project(project) {
    if (project.projectName == undefined) {
        console.log('projectName not valid');
        return;
    }

    if (innerRepresentation.isProjectOpen()) {
        notify('Project', 'close the open project before trying to load another one', 'warning');
    }
    innerRepresentation.set_project(project);
    innerRepresentation.resync_representation(function() {
        flowControl.startAll();
    });

}

function list_projects() {
    if (projectListDatatable == null) {
        projectListDatatable = $('#projectList').DataTable( {
            "ajax": {
                "url": url_get_projects,
                "dataSrc": ""
            },
            dom: "<'row'<'col-sm-8'B><'col-sm-4'f>><'row'<'col-sm-12'tr>><'row'<'col-sm-5'i><'col-sm-7'p>>",
            buttons: [
                {
                    text: '<span class="glyphicon glyphicon-file"></span> Create new project',
                    action: function ( e, dt, node, config ) {
                        // call create project modal
                        $('#modalCreateProject').modal("show");
                    },
                    className: "btn btn-success",
                },
                {
                    text: '<span class="glyphicon glyphicon-import"></span> Import project',
                    action: function ( e, dt, node, config ) {
                        // call create project modal
                        $('#modalImportProject').modal("show");
                    },
                    className: "btn btn-info",
                },
                {
                    text: '<span class="glyphicon glyphicon-folder-close "></span> Close project',
                    action: function ( e, dt, node, config ) {
                        // call create project modal
                        $('#modalListProject').modal("hide").one('hidden.bs.modal', function(event) {
                            closeProject();
                        });
                    },
                    className: "btn btn-warning",
                }
            ],
            "columns": [
                { data: "projectName" },
                { data: "projectInfo" },
                {
                    data: "creationTimestamp",
                    render: function(data, type, row) {
                        var d = new Date(parseInt(data)*1000);
                        return type === "display" || type === "filter" ?
                            d.toLocaleString() : d;
                    }
                },
                { data: "processNum" },
                {
                    data: "Action",
                    render: function(data, type, row, meta) {
                        return '<button type="button" class="btn btn-success btn-datatable" onclick="editProject('+meta.row+')" title="Edit project">'+
                                    '<span class="glyphicon glyphicon-edit"></span>'+
                                '</button>'+
                                '<button type="button" class="btn btn-info btn-datatable" style="margin-left: 5px;" title="Export project" onclick="exportProject('+meta.row+')">'+
                                    '<span class="glyphicon glyphicon-export"></span>'+
                                '</button>'+
                                '<button type="button" class="btn btn-danger btn-datatable" style="margin-left: 5px;" title="Delete project" onclick="deleteProject('+meta.row+')">'+
                                    '<span class="glyphicon glyphicon-trash"></span>'+
                                '</button>';
                    }

                }
            ]
        });
        projectListDatatable.on('dblclick', 'tr', function (event) {
            if (event.originalEvent.target.localName == 'button') { // catch button click
                return
            }
            var row = projectListDatatable.row( this ).data();
            if (row != undefined) {
                $('#modalListProject').modal("hide");
                load_project(row);
            }
        });
    } else {
        projectListDatatable.ajax.reload();
    }
}

function editProject(rowID) {
    var rowData = projectListDatatable.row(rowID).data();
    var newProjectName = prompt("Enter new project name:", rowData.projectName);
    if (newProjectName == null || newProjectName == "" || newProjectName == rowData.projectName) {
        // User cancelled the prompt
    } else {
        // send rename operation
        var data = rowData;
        data.newProjectName = newProjectName;
        execute_operation('rename', data);
    }
}

function deleteProject(rowID) {
    var rowData = projectListDatatable.row(rowID).data();
    if(confirm('Delete project \"'+rowData.projectName+'\"')) {
        if(innerRepresentation.project.projectUUID == rowData.projectUUID) {
            closeProject();
        }
        execute_operation('delete', rowData);
    }
}

function createProject() {
    if (validateForm('formCreateProject')) {
        var formID = 'formCreateProject';
        var formData = getFormData(formID);
        $('#'+formID)[0].reset();
        $('#modalCreateProject').modal("hide");
        list_projects();
        execute_operation('create', formData);
    }
}

function closeProject() {
    $.getJSON( url_close_project, {}, function( data ) {
        innerRepresentation.clear();
        $('#projectName').text("");
        alertManager.close_listener();
        setTimeout(function() {
            location.reload(true);
        }, 1000);
    });
}

function importProject() {
    send_file('importForm', url_upload_project, function(response) {
        if (response.status) {
            notify('Project upload Sucess', '', 'success');
            list_projects();
        } else {
            notify('Project upload Error:', response.message, 'danger');
        }
    });
}

function exportProject(rowID) {
    var rowData = projectListDatatable.row(rowID).data();
    console.log('performing ajax');
    $.ajax({
        url: url_download_file+'?projectUUID='+rowData.projectUUID,
        success: function() {
            document.location.href = url_download_file+'?projectUUID='+rowData.projectUUID;
        },
        error: function(response) {
            console.log(response);
            notify('Project download failure:', 'something wrong happens', 'danger');
        }
    });
}

function show_projects() {
    list_projects();
    try { // modal already initialized
        $('#'+'modalListProject').data('bs.modal').options.backdrop = true;
    } catch(err) { /* do nothing */ }
    $('#'+'modalListProject').modal('show');
}

function force_project_select() {
    list_projects();
    try { // modal already initialized
        $('#'+'modalListProject').data('bs.modal').options.backdrop = 'static';
    } catch(err) { /* do nothing */ }
    $('#'+'modalListProject').modal({show: true, backdrop: 'static'});
}
