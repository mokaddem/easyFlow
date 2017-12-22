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

// edgeData = {from: nodeID, to: nodeID}
// function addEdge(edgeData) {
//     innerRepresentation.edges.add({
//         from: edgeData.from,
//         to: edgeData.to,
//         arrows: {
//             to: {enabled: true, type:'arrow'}
//         },
//     });
// }

// function addNode(nodeData) {
//     i = parseInt(nodeData.id);
//     innerRepresentation.nodes.add({
//         id: nodeData.id,
//         image: construct_node(
//             'Module_'+String(i),
//             String(i*2)+' bytes / ' + String(i*3)+' bytes',
//             String(i*5)+' / ' + String(i*4),
//             String(i*i*i) + ' sec',
//         ),
//         x: nodeData.x,
//         y: nodeData.y,
//         shape: 'image',
//         physics: false,
//         mass: 3
//     });
// }

// function addBuffer(edgeData) {
//     if (edgeData.id === undefined) {
//         alert('no id');
//     }
//     if (edgeData.x === undefined || edgeData.y === undefined) {
//         var centerCoord = getCenterCoord(edgeData.from, edgeData.to);
//         edgeData.x = centerCoord.x;
//         edgeData.y = centerCoord.y;
//     }
//     var i = Math.floor((1 + Math.random()));
//     innerRepresentation.nodes.add({ // add the buffer between the 2 nodes
//         id: edgeData.id,
//         image: construct_buffer(
//             'Buffer',
//             String(i*2)+' bytes / ' + String(i*3)+' bytes',
//             String(i*5)+' / ' + String(i*4),
//         ),
//         x: edgeData.x,
//         y: edgeData.y,
//         shape: 'image',
//         physics: false,
//         mass: 1,
//         size: 15
//     });
//     innerRepresentation.edges.add({ // link nodes to buffer
//         from: edgeData.from,
//         to: edgeData.id,
//         arrows: {
//             to: {enabled: true, type:'arrow'}
//         },
//     });
//     innerRepresentation.edges.add({
//         from: edgeData.id,
//         to: edgeData.to,
//         arrows: {
//             to: {enabled: true, type:'arrow'}
//         },
//     });
// }

function draw() {
    // edges = [];
    // var connectionCount = [];

    // nodes = new vis.DataSet();
    // edges = new vis.DataSet();
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
            diamonds: {
                color: {background:'red',border:'white'},
                shape: 'diamond'
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
            enabled: true,
            initiallyActive: true,
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
        console.log(params);
        selectedNodes = params.nodes;
        $('#selectedNodeName').text(selectedNodes)
    });
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
