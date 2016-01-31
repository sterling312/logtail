function onopen(evt){
}
var table = {};

function separate_ticker(evt){
    var $td = $('<div></div>').text(evt.data.toUpperCase());
    var price = JSON.parse(evt.data);
    var ticker = Object.keys(price)[0];
    if (ticker in table){
        var last_price = JSON.parse(table[ticker].children().first().text())[ticker.toUpperCase()];
        table[ticker].prepend($td);
        if (price[ticker] > last_price){
            $td.addClass('positive');
            setTimeout(function(){$td.removeClass('positive');},1000);
        } else if (price[ticker] < last_price) {
            $td.addClass('negative');
            setTimeout(function(){$td.removeClass('negative');},1000);
        };
        if (table[ticker].children().length>10){
            table[ticker].children().last().remove();
        };
    }else{
        var $tr = $('<span class="ticker"></span>').attr('id', ticker);
        $tr.css('margin-left', $('div.ticker').children().length*150);
        $tr.append($td);
        table[ticker] = $tr;
        $('div.ticker').prepend($tr);
    };
}

function single_ticker(evt){
    var $td = $('<div></div>').text(evt.data);
    var $table = $('div.ticker');
    $table.prepend($td);
    if ($table.children().length>10){
        $table.children().last().remove();
    };
}

function onmessage(evt){
    if (evt.data){
        //single_ticker(evt);
        separate_ticker(evt);
    }else{
    };
}

var ws;
$(document).ready(function(){
    ws = new WebSocket($('div#ws_url').text());
    ws.onopen = onopen;
    ws.onmessage = onmessage;
});
