class FlowControl {
    constructor() {
        this.updateSocket = io.connect('http://' + document.domain + ':' + location.port + '/update');

        this.updateSocket.on('update', function(msg) {
            console.log('Received: ' + msg.data);
            var state = msg.state;
        });
    }

    update() {
        this.updateSocket.emit('updateRequest', {data: "Here's some text that the server is urgently awaiting!"});
        return false;
    }

    handleDrop(data) {
        if (data.type == 'process') {
            this.execute_operation('createProcess', data)
            .done(function(responseData, textStatus, jqXHR) {
                // set correct fields depending on the server's response
                var nodeData = mergeInto(data, responseData);
                innerRepresentation.addNode(nodeData);
            })
            .fail(function() {
                console.log( "An error occured" );
            });
        } else {
            console.log(data);
        }
    }

    execute_operation(operation, data) {
        data.operation = operation;
        return $.ajax({
            type: "POST",
            url: url_flow_operation,
            data: JSON.stringify(data),
            contentType: 'application/json; charset=utf-8',
            beforeSend: function() { toggle_loading(true); },
            complete: function() { toggle_loading(false); }
        });
    }
}
