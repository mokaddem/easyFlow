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

function load_project(project) {
    if (project.projectName == undefined) {
        console.log('projectName not valid');
        return;
    }
    toggle_loading(true);
    innerRepresentation.projectName = project.projectName;
    $.getJSON( url_load_network, {projectFilename: project.projectFilename}, function( data ) {
        console.log(data);
        console.log(data.projectInfo);
        $('#projectName').text(project.projectName);
        $('#projectName').append('<small>'+data.projectInfo+'</small>');
        innerRepresentation.load_network(data.processes);
        toggle_loading(false);
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
                    className: "btn btn-info",
                },
                {
                    text: '<span class="glyphicon glyphicon-open"></span> Import project',
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
                        return '<button type="button" class="btn btn-success btn-datatable" onclick="editProject('+meta.row+')">'+
                                    '<span class="glyphicon glyphicon-edit"></span>'+
                                '</button>'+
                                '<button type="button" class="btn btn-danger btn-datatable" style="margin-left: 5px;" onclick="deleteProject('+meta.row+')">'+
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
            $('#modalListProject').modal("hide");
            load_project(row);
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
        location.reload();
    });
}

function importProject() {
    send_file('importForm', url_upload_project);
}
