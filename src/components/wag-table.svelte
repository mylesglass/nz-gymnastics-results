<script>
	import Grid from 'gridjs-svelte';
	import { csvGenerator } from '../csvGenerator';
	import { onMount } from 'svelte';

	let grid;

	export let dataset = [
		{
			'gnz-id': 'no data'
		}
	];

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
			id: 'level',
			name: 'STEP'
		},
		{
			id: 'division',
			name: 'Division'
		},
		{
			id: 'aa-score',
			name: 'AA',
			formatter: (cell) => {
						if(isNaN(cell)) {
							return cell
						} else {
							return `${cell.toFixed(3)}`
						}
					}
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
			name: 'Club',
			width : '200px'
		},
		,
		{
			id: 'level',
			name: 'STEP'
		},

		{
			id: 'division',
			name: 'Division'
		},
		{
			id: 'competition',
			name: 'Competition',
			formatter: (cell) => {
				if(cell.length > 28) {
					return `${cell.substring(0, 28)}...`
				}	
				else {
					return cell;
				}
			},
			width: '250px'
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
					name: 'D',
					formatter: (cell) => {
						if(isNaN(cell)) {
							return cell
						} else {
							return `${cell.toFixed(1)}`
						}
					}
				},
				{
					id: 'v-total',
					name: 'Total',
					formatter: (cell) => {
						if(isNaN(cell)) {
							return cell
						} else {
							return `${cell.toFixed(3)}`
						}
					}
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
					name: 'D',
					formatter: (cell) => {
						if(isNaN(cell)) {
							return cell
						} else {
							return `${cell.toFixed(1)}`
						}
					}
				},
				{
					id: 'ub-total',
					name: 'Total',
					formatter: (cell) => {
						if(isNaN(cell)) {
							return cell
						} else {
							return `${cell.toFixed(3)}`
						}
					}
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
					name: 'D',
					formatter: (cell) => {
						if(isNaN(cell)) {
							return cell
						} else {
							return `${cell.toFixed(1)}`
						}
					}
				},
				{
					id: 'bb-total',
					name: 'Total',
					formatter: (cell) => {
						if(isNaN(cell)) {
							return cell
						} else {
							return `${cell.toFixed(3)}`
						}
					}
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
					name: 'D',
					formatter: (cell) => {
						if(isNaN(cell)) {
							return cell
						} else {
							return `${cell.toFixed(1)}`
						}
					}
				},
				{
					id: 'fx-total',
					name: 'Total',
					formatter: (cell) => {
						if(isNaN(cell)) {
							return cell
						} else {
							return `${cell.toFixed(3)}`
						}
					}
				}
			]
		},
		{
			name: 'All Around',
			columns: [
				{
					id: 'aa-rank',
					name: 'Rank'
				},
				{
					id: 'aa-score',
					name: 'AA Score',
					formatter: (cell) => {
						if(isNaN(cell)) {
							return cell
						} else {
							return `${cell.toFixed(3)}`
						}
					}
				}
			]
		},
	];

	const simpleStyle = {
		td: {
			'font-size': '1em'
		}
	};

	const detailedStyle = {
		th: {
			padding: '2px 2px',
			'font-size': '0.7em'
		},
		td: {
			'font-size': '0.7em',
			padding: '6px 2px'
		}
	};

	let currentViewMode = 'detailed';
	let currentColumns = detailedColumns;
	let currentStyle = detailedStyle;

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
		columns: currentColumns,
		search: true
	};

	let drawerToggle = false;

	// selection variables
	let selectedClub = 'All'
	let selectedRegion = 'All';
	let selectedCompetition = 'All';
	let selectedLevel = 'All';
	let selectedDivision = 'All';

	let lookupObj;

	let clubs = [
		'All',
	];
	
	let competitions, divisions, levels, regions = {};

	onMount(() => {
		let lookup = {};
		for (let i = 0; i < dataset.length; i++) {
			let jsontext = `{"club" : ${dataset[i].club}, "competition": ${dataset[i].competition}, "division": ${dataset[i].division}, "level": ${dataset[i].level}}`;
			lookup[jsontext] = true;
		}
		lookupObj = Object.keys(lookup);
		console.log(lookupObj);
	})

	function updateTableData() {
		let filteredData = dataset;

		if (selectedClub != 'All') {
			filteredData = filteredData.filter(row => row.club === selectedClub);
		}

		if (selectedDivision != 'All') {
			filteredData = filteredData.filter(row => row.division === selectedDivision);
		}

		if (selectedLevel != 'All') {
			filteredData = filteredData.filter(row => row.level === selectedLevel);
		}

		if (selectedCompetition != 'All') {
			filteredData = filteredData.filter(row => row.competition === selectedCompetition);
		}

		pkg.data = filteredData;
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

<div class="drawer">
	<input id="my-drawer" type="checkbox" class="drawer-toggle" bind:checked={drawerToggle} />
	<div class="drawer-content">
		<label for="my-drawer" class="mt-2 btn btn-primary drawer-button ">Filter results</label>
		<Grid {...pkg} bind:instance={grid} />
	</div>
	<div class="drawer-side">
		<label for="my-drawer" class="drawer-overlay" />
		<ul class="menu p-4 overflow-y-auto w-80 bg-base-100 text-base-content">
			<!-- Sidebar content here -->
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
								checked
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
					<select
						name="club-select"
						class="select select-bordered w-full max-w-xs"
						bind:value={selectedClub}
						on:change={updateTableData}
					>
						<option selected>All</option>
						{#each clubs as club}
							<option>{club}</option>
						{/each}
					</select>
					<p>STEP</p>
					<select
						name=""
						id=""
						class="select select-bordered w-full max-w-xs"
						bind:value={selectedLevel}
						on:change={updateTableData}
					>
						<option selected>All</option>
						<option>1</option>
						<option>2</option>
					</select>
					<p>Division</p>
					<select
						name=""
						id=""
						class="select select-bordered w-full max-w-xs"
						bind:value={selectedDivision}
						on:change={updateTableData}
					>
						<option selected>All</option>
						<option>OVER</option>
						<option>UNDER</option>
					</select>
					<p>Competition</p>
					<select
						name=""
						id=""
						class="select select-bordered w-full max-w-xs"
						bind:value={selectedCompetition}
						on:change={updateTableData}
					>
						<option selected>All</option>
						<option>OVER</option>
						<option>UNDER</option>
					</select>
					<p>Region</p>
					<select
						name=""
						id=""
						class="select select-bordered w-full max-w-xs"
						bind:value={selectedRegion}
						on:change={updateTableData}
						disabled
					>
						<option selected>Unavailable</option>
					</select>
				</div>

				<!-- Buttons -->
				<div>
					<!-- Apply -->

					<!-- Download -->
					<button class="btn btn-secondary mt-4" on:click={downloadCSV}
						>Download CSV of current table</button
					>
				</div>
			</form>
		</ul>
	</div>
</div>

<style global>
	@import 'https://cdn.jsdelivr.net/npm/gridjs/dist/theme/mermaid.min.css';
</style>
