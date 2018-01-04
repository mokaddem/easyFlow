function draw() {
    innerRepresentation = new InnerRepresentation();
    flowControl = new FlowControl();

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
        interaction: { multiselect: true},
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
                    var r = confirm("Do you want to connect the node to itself?");
                    if (r === true) {
                        callback(edgeData);
                    }
                }
                else {
                    flowControl.add_link(edgeData);
                }
            },
            editEdge: function(edgeData,callback) {
            }
        }
    };

    network = new vis.Network(container, data, options);

    // add event listeners
    network.on("selectNode", function (params) {
        handleNodeSelection(params);
    });
    network.on("deselectNode", function (params) {
        handleNodeSelection(params);
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

    // generique alerts manager that displays alerts
    alertManager = new AlertsManager();


    //try to load project based on cookies
    init_load();

}
// setTimeout(function(){innerRepresentation.update();}, 6000);
// setTimeout(function(){network.addNodeMode();}, 6000);

function handleNodeSelection(params) {
    selectedNodes = params.nodes;
    if(selectedNodes.length > 1) {
        var selectedNodesText = "";
        var selectedNodeType;
        selectedNodes.map(function(value, index, arr) {
            if (index == 0) {  // check if same node type
                selectedNodeType = innerRepresentation.nodeType(value);
            }

            if (innerRepresentation.nodeType(value) != selectedNodeType) {
                return false; // skip
            }
            if (index < arr.length-1) {
                selectedNodesText += innerRepresentation.processObj[value]+', ';
            } else {
                selectedNodesText += innerRepresentation.processObj[value];
                }
        });
        $('#selectedNodeName').text(selectedNodesText);
    }
    $('#selectedNodeName').text(innerRepresentation.processObj[selectedNodes]);
}

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
