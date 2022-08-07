<script>
	import Table2 from '../components/table2.svelte';
	import dataset from '$lib/data/result-data.json';
</script>

<div>
	<Table2 {dataset} />
</div>