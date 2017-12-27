function construct_node(moduleName, bytes, flowItem, time) {
    var replaced_svg = raw_module_svg.replace('\{\{moduleName\}\}', moduleName);
    var replaced_svg = replaced_svg.replace('\{\{bytes\}\}', bytes);
    var replaced_svg = replaced_svg.replace('\{\{flowItem\}\}', flowItem);
    var replaced_svg = replaced_svg.replace('\{\{time\}\}', time);
    var url = "data:image/svg+xml;charset=utf-8,"+ encodeURIComponent(replaced_svg);
    return url
}

function construct_buffer(bufferName, bytes, flowItem) {
    var replaced_svg = raw_buffer_svg.replace('\{\{bufferName\}\}', bufferName);
    var replaced_svg = replaced_svg.replace('\{\{bytes\}\}', bytes);
    var replaced_svg = replaced_svg.replace('\{\{flowItem\}\}', flowItem);
    var url = "data:image/svg+xml;charset=utf-8,"+ encodeURIComponent(replaced_svg);
    return url
}

function getCenterCoord(fromID, toID) {
    var pos = network.getPositions([fromID, toID]);
    var centerX = pos[fromID].x + (pos[toID].x - pos[fromID].x)/2;
    var centerY = pos[fromID].y + (pos[toID].y - pos[fromID].y)/2;
    return {x: centerX, y: centerY};
}

function draw() {
    innerRepresentation = new InnerRepresentation();

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
                nodeData.group = 'diamonds'
                var span = document.getElementById('operation');
                var idInput = document.getElementById('node-id');
                var labelInput = document.getElementById('node-label');
                var saveButton = document.getElementById('saveButton');
                var cancelButton = document.getElementById('cancelButton');
                var div = document.getElementById('network-popUp');
                span.innerHTML = "Add Node";
                idInput.value = nodeData.id;
                labelInput.value = nodeData.label;
                saveButton.onclick = saveData.bind(this,nodeData,callback);
                cancelButton.onclick = clearPopUp.bind();
                div.style.display = 'block';
            },
            editNode: function(nodeData, callback) {
                var span = document.getElementById('operation');
                var idInput = document.getElementById('node-id');
                var labelInput = document.getElementById('node-label');
                var saveButton = document.getElementById('saveButton');
                var cancelButton = document.getElementById('cancelButton');
                var div = document.getElementById('network-popUp');
                span.innerHTML = "Edit Node";
                idInput.value = data.id;
                labelInput.value = data.label;
                saveButton.onclick = saveData.bind(this,data,callback);
                cancelButton.onclick = clearPopUp.bind();
                div.style.display = 'block';
            },
            addEdge: function(edgeData, callback) {
                if (edgeData.from === edgeData.to) {
                    var r = confirm("Do you want to connect the node to itself?");
                    if (r === true) {
                        callback(edgeData);
                    }
                }
                else {
                    edgeData.id = guid();
                    innerRepresentation.addBuffer(edgeData);
                }
            },
            editEdge: function(edgeData,callback) {
                if (edgeData.from === edgeData.to) {
                    var r = confirm("Do you want to connect the node to itself?");
                    if (r === true) {
                        callback(edgeData);
                    }
                }
                else {
                    callback(edgeData);
                }
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
}
// setTimeout(function(){innerRepresentation.update();}, 6000);
setTimeout(function(){network.addNodeMode();}, 6000);

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
