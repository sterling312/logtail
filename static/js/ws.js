function onopen(evt){
}
var table = {};

function single_ticker(evt){
    var $td = $('<div></div>').text(evt.data);
    var $table = $('div.stream_object');
    $table.prepend($td);
    if ($table.children().length>50){
        $table.children().last().remove();
    };
}

function onmessage(evt){
    if (evt.data){
        single_ticker(evt);
    }else{
    };
}

var ws;
$(document).ready(function(){
    ws = new WebSocket($('div#ws_url').text());
    ws.onopen = onopen;
    ws.onmessage = onmessage;
});

