<div class="navbar bg-neutral text-neutral-content">
	<div class="flex-1">
		<a href="/" class="btn btn-ghost normal-case text-xl">{title}</a>
	</div>
	<div class="navbar-end">
		<label for="my-modal" class="btn btn-ghost btn-circle w-6 h-6 modal-button">
			<SettingsIcon />
		</label>
	</div>
</div>

<div class="overflow-x-auto mx-4">
    <WagTable perPage={perPage} dataset={dataset}/>
</div>

<!-- Modal -->
<input type="checkbox" id="my-modal" class="modal-toggle" />
<div class="modal">
	<div class="modal-box">
		<h3 class="font-bold text-lg">Table Settings</h3>

        <p class="font-bold">Results Per Page</p>
		<input type="range" min="20" max="100" bind:value={perPage} class="range range-xs" step="20" on:change={console.log(perPage)}/>
		<div class="w-full flex justify-between text-xs px-2">
			<span>20</span>
			<span>40</span>
			<span>60</span>
			<span>80</span>
			<span>100</span>
		</div>
		<div class="modal-action">
			<label for="my-modal" class="btn">Yay!</label>
		</div>
	</div>
</div>

<script>
	import SettingsIcon from '../components/icons/settings.svelte';
	import WagTable from '../components/wag-table.svelte';
    import dataset from '$lib/data/full-dataset.json';


	let title = 'WAG Results';
	let perPage = 20;
</script>
