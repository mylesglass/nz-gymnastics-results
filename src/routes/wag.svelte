<script>
	import WagTable from '../components/wag-table.svelte';
	import dataset from '$lib/data/result-data.json';

	let title = 'WAG Results';
	let perPage = 20;
</script>

<div>
	<WagTable {perPage} {dataset} />
</div>
