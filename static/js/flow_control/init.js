function draw() {
    // create a network
    var container = document.getElementById('mynetwork');
    var data = {
        nodes: innerRepresentation.nodes,
        edges: innerRepresentation.edges
    };
    var options = {
        physics:{
            barnesHut: {
              springConstant: 0.4,
              avoidOverlap: 0.9,
              damping: 1
            },
        },
        interaction: {
            multiselect: true,
            hover: true
        },
        groups: {
            process: {
            },
            buffer: {
            },
            mult_input: {
            },
            mult_output: {
            },
            remote_input: {
            },
            remote_output: {
            }
        },
        layout: {
            improvedLayout:true,
            hierarchical: {
              enabled:true,
              levelSeparation: 300,
              nodeSpacing: 200,
              blockShifting: true,
              edgeMinimization: true,
              direction: 'LR',        // UD, DU, LR, RL
              sortMethod: 'directed'   // hubsize, directed
            }
        },
        nodes: {
            shadow: true,
            chosen: {
                node: function(values, id, selected, hovering) {
                    // values.shadowSize ='10px';
                    values.shadowSize = 5;
                    if (selected) {
                        values.shadowColor = '#337ab7';
                    } else if (hovering) {
                        values.shadowColor = '#65A5FB';
                    }
                }
            }
        },
        edges: {
            color: {color: 'black'},
            shadow: true,
        },
        manipulation: {
            enabled: false,
            initiallyActive: false,
            addNode: function(nodeData, callback) {
            },
            editNode: function(nodeData, callback) {
            },
            addEdge: function(edgeData, callback) {
                if (edgeData.from === edgeData.to) {
                    var r = alert("Process recursion is not yet supported");
                }
                else {
                    flowControl.add_link(edgeData);
                }
            },
            editEdge: function(edgeData,callback) {
            },
            controlNodeStyle: {
                shape:'diamond',
                size:7,
                color: {
                    background: '#ffffff',
                    border: '#3c3c3c',
                    highlight: {
                      background: '#07f968',
                      border: '#3c3c3c'
                    }
                },
                borderWidth: 2,
            }

        }
    };

    network = new vis.Network(container, data, options);
    var options = {
        offset: {x: 0,y: 0},
        duration: 1,
        easingFunction: 'easeInOutQuad'
    };
    network.fit({animation:options});
    canvas = network.canvas.frame.canvas;
    ctx = canvas.getContext('2d');
    function changeCursor(newCursorStyle){
        $('#mynetwork').find('canvas').css( 'cursor', newCursorStyle );
    }
    network.on('hoverNode', function () {
        changeCursor('grab');
    });
    network.on('blurNode', function () {
        changeCursor('default');
    });
    network.on('hoverEdge', function () {
        changeCursor('grab');
    });
    network.on('blurEdge', function () {
        changeCursor('default');
    });
    network.on('dragStart', function () {
        changeCursor('grabbing');
    });
    network.on('dragging', function () {
        changeCursor('grabbing');
    });
    network.on('dragEnd', function (params) {
        changeCursor('grab');
        flowControl.handleNodesDrag(params.nodes);

    });

    // add event listeners
    network.on("selectNode", function (params) {
        innerRepresentation.handleNodeSelection(params);
    });
    network.on("deselectNode", function (params) {
        innerRepresentation.handleNodeSelection(params);
    });

    $( "body" ).keydown(function( event ) {
        if (!innerRepresentation.isProjectOpen()) {return;}
        if (document.activeElement.nodeName != 'BODY') { return; }
        if ( event.which == 17 ) {
            $('button[name="pipe"]').click();
        }
    });
    $( "body" ).keyup(function( event ) {
        if (!innerRepresentation.isProjectOpen()) {return;}
        if (document.activeElement.nodeName != 'BODY') { return; }
        if (event.which == 17) { // CTRL
            var btnPipe = $('button[name="pipe"]');
            btnPipe.attr('activated', true)
            btnPipe.click();
        } else if (flowControl.selected.length>0) {
            switch (event.which) {
                case 69: // e
                    $('#pcontrol_edit').click();
                    break;
                case 46: // DEL
                    if (confirm('Delete selected items?')) {
                        $('#pcontrol_delete').click();
                    }
                    break;
                case 76: // l
                    $('#pcontrol_logs').click();
                    break;
                case 80: // p
                    if (event.shiftKey) {
                        $('#pcontrol_play').click();
                    } else {
                        $('#pcontrol_pause').click();
                    }
                    break;
                case 83: // s
                    $('#pcontrol_stop').click();
                    break;
                default:
                    break;
            }
        }
    });
    $( "body" ).mouseleave(function() {
        var btnPipe = $('button[name="pipe"]');
        if (btnPipe.attr('activated') == 'true') {
            btnPipe.click();
        }
    });

    $('#pcontrol_play').click(function(){
        flowControl.play_node();
    });
    $('#pcontrol_pause').click(function(){
        flowControl.pause_node();
    });
    $('#pcontrol_stop').click(function(){
        flowControl.stop_node();
    });
    $('#pcontrol_restart').click(function(){
        flowControl.restart_node();
    });
    $('#pcontrol_clone').click(function(){
        flowControl.duplicate_selected();
    });
    $('#pcontrol_logs').click(function(){
        flowControl.get_logs();
    });
    $('#pcontrol_delete').click(function(){
        flowControl.delete_node();
    });
    $('#pcontrol_edit').click(function(){
        flowControl.edit_node();
    });
    $('#pcontrol_empty').click(function(){
        flowControl.empty_buffer();
    });

    $('#tabProcessCustomSettings').click(function(){
        $($(this).attr('href')).find('select').map(function() {
            $('#'+$(this).prop('name')+'_additional_options_'+this.value).collapse('show');
        })
    });
    $('#switch_show_realtime_log').on("change", function(){
        if ($(this).is(':checked')) {
            var process_is_selected = flowControl.selected.length > 0;
            if (process_is_selected) { // switch is checked and process is selected
                realtimeLogs = new RealtimeLogs(flowControl.selected[0])
            }
        } else {
            if (realtimeLogs !== null) {
                realtimeLogs.close_listener();
                realtimeLogs = null;
            }
        }
    });
    $("#checkboxes_log_level").find("input").on("change", function() {
        innerRepresentation.applyLogLevelFiltering();
    });

    createProcessDatatable = $("#CreateProcessTypeDatatable").DataTable({
        "paging":   false,
        "ordering": false,
        "info":     false,
        "searching":false,
        columns: [
            { data: 'label' },
            { data: 'DOM' },
            { data: 'inputType' },
            { data: 'default' },
            { data: 'dynamic_change' },
            { data: 'additional_options' },
            {
                data: "Action",
                render: function(data, type, row, meta) {
                    if (meta.row == 0) {
                        return data;
                    }
                    return '<button type="button" class="btn btn-danger btn-datatable" style="margin-left: 5px;" title="Delete project" onclick="createProcessDatatable.row($(this).parents(\'tr\')).remove().draw(false)">'+
                                '<span class="glyphicon glyphicon-trash"></span>'+
                            '</button>';
                }

            }
        ]
    });
    $("#CreateProcessType_inputType").on('change', function() {
        $("#CreateProcessType_defaultValue").attr('type', $(this).val());
    });
    $("#CreateProcessType_add_parameter").click(function() {
        param_data = {
            label:              createProcessDatatable.cell(0,0).nodes().to$().find('input').val(),
            DOM:                createProcessDatatable.cell(0,1).nodes().to$().find('select').val(),
            inputType:         createProcessDatatable.cell(0,2).nodes().to$().find('select').val(),
            default:      createProcessDatatable.cell(0,3).nodes().to$().find('input').val(),
            dynamic_change:     createProcessDatatable.cell(0,4).nodes().to$().find('input').prop('checked'),
            additional_options: createProcessDatatable.cell(0,5).nodes().to$().find('input').val()
        }
        createProcessDatatable.row.add(param_data).draw( false );
        createProcessDatatable.cell(0,0).nodes().to$().find('input').val('');
        createProcessDatatable.cell(0,1).nodes().to$().find('select').val('input');
        createProcessDatatable.cell(0,2).nodes().to$().find('select').val('text');
        createProcessDatatable.cell(0,3).nodes().to$().find('input').val('');
        createProcessDatatable.cell(0,4).nodes().to$().find('input').prop('checked', false);
        createProcessDatatable.cell(0,5).nodes().to$().find('input').val('');
    })

    $('button[name="pipe"]').on("click", function (eventObject) {
        var btnPipe = $(eventObject.currentTarget);
        if (btnPipe.attr('activated') == 'true' ){
            btnPipe.attr('activated', 'false');
            toggle_btn_pipe(false);
            changeCursor('default');
            network.disableEditMode();
        } else {
            btnPipe.attr('activated', 'true');
            toggle_btn_pipe(true);
            changeCursor('copy');
            network.addEdgeMode();
        }

    });

    $('#switch_simplified_view').change(function() {
        innerRepresentation.resync_representation();
    });

    // draggable
    $('.btnDraggable').draggable({
        cancel:false,
        stack: "#mynetwork",
        revert: false,
        revertDuration: 100,
        scroll: false,
        cursor: "move",
        helper: "clone",
        zIndex: 5000,
        cursorAt: {
            top: 31,
            left: 31
        }
    });
    $( "#mynetwork" ).droppable({
            classes: {
                "ui-droppable-hover": "ui-state-hover"
            },
            drop: function( event, ui ) {
                var btn_type = ui.draggable.attr('name');
                var drop_position = ui.position;
                var ResDOMtoCanvas = network.DOMtoCanvas({
                    x: drop_position.left+100, //
                    y: drop_position.top-50
                });
                var nodeData = {
                    type: btn_type,
                    x: ResDOMtoCanvas.x,
                    y: ResDOMtoCanvas.y
                };
                flowControl.handleDrop(nodeData);
            }
    });
    $('#controlPanel').draggable({
        stack: "#mynetwork",
        revert: false,
        scroll: false,
        cursor: "move",
        zIndex: 5000,
    });

    processTypeDatable = $('#processTypeDatable').DataTable({
        dom: "<'row'<'col-sm-4'i><'col-sm-4'f><'col-sm-4'p>><'row'<'col-sm-12'tr>>"
    });

    $('#showDataTableProcessType').click(function() {
        $('#processTypeDatableDiv').slideToggle('fast');
    })

    $('#processTypeDatable tbody').on( 'click', 'tr', function () {
        processTypeDatable.$('tr.selectedType').removeClass('selectedType');
        $(this).addClass('selectedType');
        var selectedType = processTypeDatable.rows('.selectedType').data()[0]
        $('#processTypeSelector').val(selectedType);
        $('#processTypeSelector').change();
    } );

    $('#showTableGenerateFromBash').click(function() {
        $('#tableGenerateFromBash').toggle();
    });
    networkParseBash = new vis.Network(document.getElementById('GenerateFromBashNetwork'), {nodes: new vis.DataSet(), edges: new vis.DataSet()}, {
        layout: {
            improvedLayout:true,
            hierarchical: {
            //   enabled:true,
              direction: 'LR',         // UD, DU, LR, RL
              sortMethod: 'directed'   // hubsize, directed
            }
        },
        nodes: {
          shape: 'box',
          font: {size: 24, color: '#39ff14'},
          color: {border: '#afafaf', background: '#303030'}
        },
        interaction: {dragNodes :false},
    });
    $('#bashCommandInput').on('input', function(event) {
        generate_network_from_bash_command($(this).val());
    })

}
$( document ).ready(function() {
    innerRepresentation = new InnerRepresentation();
    flowControl = new FlowControl();
    alertManager = new AlertsManager();
    init_load(); //try to load project based on cookies

    draw();

    window.onbeforeunload = function() {
        alertManager.close_listener();
        alert('Are you sure to reload?');
    }

});

function init_load() {
    if (getCookie('projectUUID') === undefined) {
        force_project_select();
    } else {
        load_project({
            projectUUID: getCookie('projectUUID'),
            projectName: getCookie('projectName')
        });
    }
}
