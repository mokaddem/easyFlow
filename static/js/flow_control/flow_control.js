class FlowControl {
    constructor() {
        this._modalSuccess = false; // shows modal result (if user clicked cancel or not)
    }

    modalStateSucess() { this._modalSuccess = true; }
    modalStateReset() { this._modalSuccess = false; }

    delete_node(uuid) {
        if (innerRepresentation.nodeType(uuid) == 'process') {
            this.execute_operation('delete_process', {puuid: uuid}, false);
        } else if ((innerRepresentation.nodeType(uuid) == 'buffer')) {
            this.execute_operation('delete_link', {buuid: uuid}, false);
        } else {
        }
    }

    add_link(linkData) {
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
                    var nodeData = responseData;
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
                    var nodeData = responseData;
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
                    var nodeData = responseData;
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

    handleModal(modalType, dropData, callback) {
        var self = this;
        var formID = 'form'+modalType;
        var formIDCustom = 'form'+modalType+'Custom';
        var modalID = 'modal'+modalType;

        $('#'+modalID).modal('show');
        add_html_based_on_json($('#processTypeSelector').val(), $('#'+formIDCustom));
        // Create custom_config html element on click
        $('#processTypeSelector').on('change', function() {
            $('#'+formIDCustom).empty();
            add_html_based_on_json($( this ).val(), $('#'+formIDCustom));
        })

        $('#'+modalID).find('button[confirm="1"]').one('click', function(event) {
            if (validateForm(formID)) {
                var formData = getFormData(formID);
                $('#'+formID)[0].reset();
                var modalData = mergeInto(dropData, formData);
                var formDataCustom = getFormData(formIDCustom);
                // $('#'+formIDCustom)[0].reset();
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
