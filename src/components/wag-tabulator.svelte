<script>
	import { TabulatorFull as Tabulator } from 'tabulator-tables';
	import { onMount } from 'svelte';

	export let data, columns;

	let tableComponent;

	onMount(() => {
		new Tabulator(tableComponent, {
			data: data, //link data to table
			reactiveData: true, //enable data reactivity
			columns: columns, //define table columns
            layout: 'fitColumns'
		});
	});
</script>

<div class="h-screen">
	<div bind:this={tableComponent} />
</div>

<div>
    <p class="text-xl">Gucci Gang</p>
</div>
<svelte:head>
	<link
		href="https://unpkg.com/tabulator-tables@4.9.1/dist/css/tabulator.min.css"
		rel="stylesheet"
	/>
</svelte:head>
