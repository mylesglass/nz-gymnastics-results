<script>
	import Grid from 'gridjs-svelte';
	import { csvGenerator } from '../csvGenerator';
	import AppScore from '../components/app-score.svelte';
	import { SvelteWrapper } from 'gridjs-svelte/plugins';

	let grid;

	let clubs = [
		'Capital Gymnastics',
		'Christchurch School of Gymnastics',
		'Dunedin Gymnastics Academy',
		'Gymnastics Nelson',
		'Harbour City Gymnastics'
	];

	export let dataset = [
		{
			'gnz-id': 'no data'
		}
	];

	$: console.log(dataset);

	export let perPage = 10;

	const simpleColumns = [
		{
			id: 'gnz-id',
			name: 'ID'
		},
		{
			id: 'name',
			name: 'Name'
		},
		{
			id: 'club',
			name: 'Club'
		},
		{
			id: 'competition',
			name: 'Competition'
		},
		{
			id: 'step',
			name: 'STEP'
		},
		{
			id: 'division',
			name: 'Division'
		},
		{
			id: 'aa-score',
			name: 'AA'
		}
	];

	const detailedColumns = [
		{
			id: 'gnz-id',
			name: 'ID'
		},
		{
			id: 'name',
			name: 'Name'
		},
		{
			id: 'club',
			name: 'Club'
		},
		,
		{
			id: 'step',
			name: 'STEP'
		},

		{
			id: 'division',
			name: 'Division'
		},
		{
			id: 'competition',
			name: 'Competition'
		},
		{
			id: 'round-type',
			name: 'Round Type'
		},
		{
			name: 'Vault',
			columns: [
				{
					id: 'v-rank',
					name: 'Rank'
				},
				{
					id: 'v-d',
					name: 'D'
				},
				{
					id: 'v-total',
					name: 'Total'
				}
			]
		},
		{
			name: 'Uneven Bars',
			columns: [
				{
					id: 'ub-rank',
					name: 'Rank'
				},
				{
					id: 'ub-d',
					name: 'D'
				},
				{
					id: 'ub-total',
					name: 'Total'
				}
			]
		},
		{
			name: 'Balance Beam',
			columns: [
				{
					id: 'bb-rank',
					name: 'Rank'
				},
				{
					id: 'bb-d',
					name: 'D'
				},
				{
					id: 'bb-total',
					name: 'Total'
				}
			]
		},
		{
			name: 'Floor Exercise',
			columns: [
				{
					id: 'fx-rank',
					name: 'Rank'
				},
				{
					id: 'fx-d',
					name: 'D'
				},
				{
					id: 'fx-total',
					name: 'Total'
				}
			]
		},
		{
			id: 'aa-score',
			name: 'AA'
		}
	];

	let currentViewMode = 'simple';
	let currentColumns = simpleColumns;

	const simpleStyle = {
		td: {
			'font-size': '1em'
		}
	};

	const detailedStyle = {
		td: {
			'font-size': '0.7em',
			'padding': '2px 2px'
		}
	};

	let currentStyle = simpleStyle;

	const tableHeader = [
		'gnz-id',
		'name',
		'club',
		'step',
		'division',
		'competition',
		'round-type',
		'day',
		'v-total',
		'v-d',
		'v-rank',
		'ub-total',
		'ub-d',
		'ub-rank',
		'bb-total',
		'bb-d',
		'bb-rank',
		'fx-total',
		'fx-d',
		'fx-rank',
		'aa-score',
		'aa-rank',
		'date-created'
	];

	const pkg = {
		data: dataset,
		style: currentStyle,
		pagination: {
			enabled: true,
			limit: perPage
		},
		sort: {
			enabled: true
		},
		columns: currentColumns
	};

	function handleSubmit() {
		alert('hey');
	}

	function viewModeToggle() {
		if (currentViewMode === 'detailed') {
			grid
				.updateConfig({
					columns: detailedColumns,
					style: detailedStyle
				})
				.forceRender();
		} else if (currentViewMode == 'simple') {
			grid
				.updateConfig({
					columns: simpleColumns,
					style: simpleStyle
				})
				.forceRender();
		}
	}

	function downloadCSV() {
		let filename = 'wag-results-' + Date.now() + '.csv';
		let tableKeys = Object.keys(dataset[0]);
		csvGenerator(dataset, tableKeys, tableHeader, filename);
	}

	function updateResultsPerPage() {
		grid
			.updateConfig({
				pagination: {
					enabled: true,
					limit: perPage
				}
			})
			.forceRender();
	}
</script>

<div>
	<div class="flex space-x-2">
		<div class="item w-1/3 card bg-base-100">
			<div class="card-body">
				<form>
					<!-- Results per page-->
					<div>
						<p class="card-title">Results per page</p>
						<p>Alter how many results are displayed per page</p>
						<input
							type="range"
							min="20"
							max="100"
							bind:value={perPage}
							class="range range-xs"
							step="20"
							on:change={updateResultsPerPage}
						/>
						<div class="w-full flex justify-between text-xs px-2">
							<span>20</span>
							<span>40</span>
							<span>60</span>
							<span>80</span>
							<span>100</span>
						</div>
					</div>
					<!-- View Mode -->
					<div>
						<p class="card-title">View Mode</p>
						<div class="form-control">
							<label class="label cursor-pointer">
								<span class="label-text">Simple</span>
								<input
									type="radio"
									bind:group={currentViewMode}
									class="radio checked:bg-blue-500"
									checked
									value={'simple'}
									on:change={viewModeToggle}
								/>
							</label>
						</div>
						<div class="form-control">
							<label class="label cursor-pointer">
								<span class="label-text">Detailed</span>
								<input
									type="radio"
									bind:group={currentViewMode}
									class="radio checked:bg-red-500"
									value={'detailed'}
									on:change={viewModeToggle}
								/>
							</label>
						</div>
					</div>

					<!-- Filters -->
					<div>
						<p class="card-title">Filters</p>
						<p>Club</p>
						<select name="" id="" class="select select-bordered w-full max-w-xs">
							<option selected>All</option>
							{#each clubs as club}
								<option>{club}</option>
							{/each}
						</select>
						<p>Region</p>
						<select name="" id="" class="select select-bordered w-full max-w-xs">
							<option selected>All</option>
						</select>
						<p>STEP</p>
						<select name="" id="" class="select select-bordered w-full max-w-xs">
							<option selected>All</option>
							<option>1</option>
							<option>2</option>
						</select>
						<p>Division</p>
						<select name="" id="" class="select select-bordered w-full max-w-xs">
							<option selected>All</option>
							<option>OVER</option>
							<option>UNDER</option>
						</select>
					</div>
				</form>
			</div>
		</div>
		<div class="item w-1/3 card bg-base-100">
			<div class="card-body">
				<button class="btn btn-primary" on:click={downloadCSV}>Download CSV of current table</button
				>
			</div>
		</div>
	</div>

	<Grid {...pkg} bind:instance={grid} />
</div>

<style global>
	@import 'https://cdn.jsdelivr.net/npm/gridjs/dist/theme/mermaid.min.css';
</style>
