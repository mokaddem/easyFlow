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
        nodes: {
            shadow: true,
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
                    // if (r === true) {
                    //     callback(edgeData);
                    // }
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
    network.on('dragEnd', function () {
        changeCursor('grab');
    });

    // add event listeners
    network.on("selectNode", function (params) {
        innerRepresentation.handleNodeSelection(params);
    });
    network.on("deselectNode", function (params) {
        innerRepresentation.handleNodeSelection(params);
    });
    network.on("dragEnd", function (params) {
        flowControl.handleNodesDrag(params.nodes);
    });
    $('#pcontrol_play').click(function(){
        flowControl.play_node()
    });
    $('#pcontrol_pause').click(function(){
        flowControl.pause_node()
    });
    $('#pcontrol_logs').click(function(){

    });
    $('#pcontrol_delete').click(function(){
        flowControl.delete_node()
    });
    $('#pcontrol_edit').click(function(){
        flowControl.edit_node()
    });

    $('button[name="pipe"]').on("click", function (eventObject) {
        var btnPipe = $(eventObject.currentTarget);
        if (btnPipe.attr('activated') == 'true' ){
            btnPipe.attr('activated', 'false');
            toggle_btn_pipe(false);
            network.disableEditMode();
        } else {
            btnPipe.attr('activated', 'true');
            toggle_btn_pipe(true);
            network.addEdgeMode();
        }

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

/* FORM CREATION */
function clearPopUp() {
    var saveButton = document.getElementById('saveButton');
    var cancelButton = document.getElementById('cancelButton');
    saveButton.onclick = null;
    cancelButton.onclick = null;
    var div = document.getElementById('network-popUp');
    div.style.display = 'none';
}

function saveData(data,callback) {
    var idInput = document.getElementById('node-id');
    var labelInput = document.getElementById('node-label');
    var div = document.getElementById('network-popUp');
    data.id = idInput.value;
    data.label = labelInput.value;
    clearPopUp();
    callback(data);
}
