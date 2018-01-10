class FlowControl {
    constructor() {
        this.selected = [];
    }

    delete_node() {
        var uuids = this.selected;
        if (innerRepresentation.nodeType(uuids[0]) == 'process') { // uuids are the same type
            this.execute_operation('delete_process', {puuid: uuids}, false);
        } else if ((innerRepresentation.nodeType(uuids[0]) == 'buffer')) { // uuids are the same type
            this.execute_operation('delete_link', {buuid: uuids}, false);
        } else {
        }
    }

    edit_node() {
        var self = this;
        if (this.selected.length > 1) { return; /* do not edit if multiple nodes are selected */ }
        var uuid = this.selected[0];
        if (innerRepresentation.nodeType(uuid) == 'process') {
            this.query_config_and_fill_form(uuid, 'AddProcess', {type: 'process', uuid: uuid}, function() {
                var modalType = 'AddProcess';
                var modalID = 'modal'+modalType;
                $('#'+modalID).modal('show');
                self.handleModalConfirm(modalType, {puuid: uuid, update: true}, function(modalData) {
                    self.execute_operation('edit_process', modalData)
                    .done(function(responseData, textStatus, jqXHR) {
                    })
                    .fail(function() {
                        console.log( "An error occured" );
                    });
                });

            });
        } else if (innerRepresentation.nodeType(uuid) == 'buffer') {
            this.query_config_and_fill_form(uuid, 'AddLink', {type: 'buffer', uuid: uuid}, function() {
                self.handleModal('AddLink', {buuid: uuid}, function(modalData) {
                    self.execute_operation('edit_link', modalData)
                    .done(function(responseData, textStatus, jqXHR) {
                    })
                    .fail(function() {
                        console.log( "An error occured" );
                    });
                });
            });
        } else {
        }
    }

    add_link(linkData) {
        // check only one link per process
        var destProcType = innerRepresentation.processObj[linkData.to].type;
        var destConnectionNum = network.getConnectedNodes(linkData.to);
        var srcProcType = innerRepresentation.processObj[linkData.from].type;
        var srcConnectionNum = network.getConnectedNodes(linkData.from);
        // validate link creation
        if (destConnectionNum.length == 1 && destProcType != 'multiplexer_in') {
            notify('Error:', 'Only <strong>multiplexer_in</strong> are allowed to have multiple ingress connections', 'danger');
            return;
        }
        if (srcConnectionNum.length == 1 && srcProcType != 'multiplexer_out') {
            notify('Error:', 'Only <strong>multiplexer_out</strong> are allowed to have multiple egress connections', 'danger');
            return;
        }

        var self = this;
        var linkDataCorrectKeyname = {};
        linkDataCorrectKeyname.fromUUID = linkData.from;
        linkDataCorrectKeyname.toUUID = linkData.to;
        var pos = getCenterCoord(linkData.from, linkData.to)
        linkDataCorrectKeyname.x = pos.x;
        linkDataCorrectKeyname.y = pos.y;

        self.handleModal('AddLink', linkDataCorrectKeyname, function(modalData) {
            self.execute_operation('add_link', modalData)
            .done(function(responseData, textStatus, jqXHR) {
            })
            .fail(function() {
                console.log( "An error occured" );
            });
        });
    }

    handleDrop(dropData) {
        var self = this;
        if (dropData.type == 'process') {
            self.handleModal('AddProcess', dropData, function(modalData) {
                console.log(modalData);
                self.execute_operation('create_process', modalData)
                .done(function(responseData, textStatus, jqXHR) {
                })
                .fail(function() {
                    console.log( "An error occured" );
                });
            });

        } else if (dropData.type == 'mult_input') {
            self.handleModal('AddMultInput', dropData, function(modalData) {
                console.log(modalData);
                self.execute_operation('create_mult_input', modalData)
                .done(function(responseData, textStatus, jqXHR) {
                })
                .fail(function() {
                    console.log( "An error occured" );
                });
            });
        } else if (dropData.type == 'mult_output') {
            self.handleModal('AddMultOutput', dropData, function(modalData) {
                console.log(modalData);
                self.execute_operation('create_mult_output', modalData)
                .done(function(responseData, textStatus, jqXHR) {
                })
                .fail(function() {
                    console.log( "An error occured" );
                });
            });

        } else if (dropData.type == 'remote_input') {
        } else if (dropData.type == 'remote_output') {
        } else {
            console.log(dropData);
        }
    }

    query_config_and_fill_form(uuid, modalType, uuidData, form_callback) {
        var formID = 'form'+modalType;
        var formIDCustom = 'form'+modalType+'Custom';
        return $.ajax({
            type: "POST",
            url: url_get_node_configuration,
            data: JSON.stringify(uuidData),
            contentType: 'application/json; charset=utf-8',
        }).done(function( data ) {
                fillForm(formID, formIDCustom, data);
                form_callback();
            }
        );
    }

    handleModal(modalType, dropData, callback) {
        var formID = 'form'+modalType;
        var formIDCustom = 'form'+modalType+'Custom';
        var modalID = 'modal'+modalType;

        $('#'+modalID).modal('show');
        $('#'+formIDCustom).empty();
        var pSelector = $('#'+modalID).find('[name="type"]');
        add_html_based_on_json(pSelector.val(), $('#'+formIDCustom));
        // Create custom_config html element on click
        $('#processTypeSelector').on('change', function() {
            $('#'+formIDCustom).empty();
            add_html_based_on_json($( this ).val(), $('#'+formIDCustom));
        })

        this.handleModalConfirm(modalType, dropData, callback);
    }

    handleModalConfirm(modalType, dropData, callback) {
        var formID = 'form'+modalType;
        var formIDCustom = 'form'+modalType+'Custom';
        var modalID = 'modal'+modalType;
        var confirmBtn = $('#'+modalID).find('button[confirm="1"]');
        // set correct button text
        if (dropData.update) {
            confirmBtn.text('Update');
        } else {
            confirmBtn.text('Create');
        }
        // main logic
        confirmBtn.one('click', function(event) {
            if (validateForm(formID)) {
                var formData = getFormData(formID);
                $('#'+formID)[0].reset();
                var modalData = mergeInto(dropData, formData);
                var formDataCustom = getFormData(formIDCustom);
                $('#'+formIDCustom).empty();
                var modalData = mergeInto(modalData, {custom_config: formDataCustom });
                $('#'+modalID).modal('hide');
                callback(modalData);
            }
        });
    }

    handleNodesDrag(nodes) {
        var position = network.getPositions(nodes);
        for (var nodeUUID of nodes) {
            var data = {
                uuid: nodeUUID,
                nodeType: innerRepresentation.nodeType(nodeUUID),
                x: position[nodeUUID].x,
                y: position[nodeUUID].y
            }
            this.execute_operation('node_drag', data, true)
        }
    }

    execute_operation(operation, data, quick) {
        quick = quick === undefined ? false : quick;
        data.operation = operation;
        return $.ajax({
            type: "POST",
            url: url_flow_operation,
            data: JSON.stringify(data),
            contentType: 'application/json; charset=utf-8',
            beforeSend: function() { toggle_loading(true, quick); },
            complete: function() {
                toggle_loading(false, quick);
                if (!quick) {
                    innerRepresentation.resync_representation();
                }
            }
        });
    }

    startAll() {
        var data = {};
        data.operation = 'start_all';
        $.ajax({
            type: "POST",
            url: url_flow_operation,
            data: JSON.stringify(data),
            contentType: 'application/json; charset=utf-8'
        });
    }
}
