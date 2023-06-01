<script>
	import WagTabulator from '../components/wag-tabulator.svelte';
	import data from '$lib/data/short-dataset.json';

    const columns = [
        {title:"GNZ #", field:"gnz-id", sorter:"number", width: 80},
        {title:"Name", field:"name", sorter:"string"},
        {title:"Club", field:"club", sorter:"string"},
        {title:"STEP", field:"level", sorter:"number", width: 100},
        {title:"Division", field:"division", sorter:"string", width: 100},
        {title:"Competition", field:"competition", sorter:"string", width: 300},
        {title:"Round Type", field:"round-type", sorter:"string", visible: false},
        {title:"Day", field:"day", sorter:"number", visible: false}, 
        /**
        {
            title:"Vault",
            headerHozAlign:"center",
            columns:[
                {title:"Score", field:"v-total", hozAlign:"right"},
                {title:"Diff.", field:"v-d", hozAlign:"center"},
                {title:"Rank", field:"v-rank", hozAlign:"center"}
            ]
        }*/
    ]

    /***
        {title:"Vault Score", field:"v-total", sorter:"number"},
        {title:"Vault Difficulty", field:"v-d", sorter:"number"},
        {title:"Vault Rank", field:"v-rank", sorter:"string"},
        {title:"Uneven Bars Score", field:"ub-total", sorter:"number"},
        {title:"Uneven Bars Difficulty", field:"ub-d", sorter:"number"},
        {title:"Uneven Bars  Rank", field:"ub-rank", sorter:"string"},
        {title:"Beam Score", field:"bb-total", sorter:"number"},
        {title:"Beam Difficulty", field:"bb-d", sorter:"number"},
        {title:"Beam Rank", field:"bb-rank", sorter:"string"},
        {title:"Floor Score", field:"fx-total", sorter:"number"},
        {title:"Floor Difficulty", field:"fx-d", sorter:"number"},
        {title:"Floor Rank", field:"fx-rank", sorter:"string"},
        {title:"AA Score", field:"aa-score", sorter:"number"},
        {title:"AA Rank", field:"aa-rank", sorter:"string"}, **/
</script>

<WagTabulator {data} {columns} />
