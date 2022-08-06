<div class="navbar bg-neutral text-neutral-content">
	<div class="flex-1">
		<a href="/" class="btn btn-ghost normal-case text-xl">{title}</a>
	</div>
	<div class="navbar-end">
	</div>
</div>

<div class="overflow-x-auto mx-4">
    <WagTable perPage={perPage} dataset={dataset}/>
</div>

<script>
	import WagTable from '../components/wag-table.svelte';
    import dataset from '$lib/data/result-data.json';


	let title = 'WAG Results';
	let perPage = 20;
</script>
