<script>
	import Grid from 'gridjs-svelte';
	import { csvGenerator } from '../csvGenerator';
	import { SvelteWrapper } from "gridjs-svelte/plugins";
	import { h } from 'gridjs';

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
			name: 'Competition',
			formatter: (cell) => {
				if (cell.length > 28) {
					return `${cell.substring(0, 28)}...`;
				} else {
					return cell;
				}
			}
		},
		{
			id: 'level',
			name: 'STEP'
		},
		{
			id: 'division',
			name: 'Division'
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
				if (cell.length > 28) {
					return `${cell.substring(0, 28)}...`;
				} else {
					return cell;
				}
			},
			width: '11%'
		},
		{
			name: 'Vault',
			columns: [
				{
					id: 'v-rank',
					name: 'Rnk'
				},
				{
					id: 'v-d',
					name: 'D',
					formatter: (cell) => {
						return formatCell(cell, 1);
					}
				},
				{
					id: 'v-total',
					name: 'Total',
					formatter: (cell) => {
						return formatCell(cell, 3);
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
						return formatCell(cell, 1);
					}
				},
				{
					id: 'ub-total',
					name: 'Total',
					formatter: (cell) => {
						return formatCell(cell, 3);
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
						return formatCell(cell, 1);
					}
				},
				{
					id: 'bb-total',
					name: 'Total',
					formatter: (cell) => {
						return formatCell(cell, 3);
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
						return formatCell(cell, 1);
					}
				},
				{
					id: 'fx-total',
					name: 'Total',
					formatter: (cell) => {
						return formatCell(cell, 3);
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
						return formatCell(cell, 3);
					}
				}
			]
		}
	];

	function formatCell(cell, decimalPlace) {
		if (isNaN(cell) || !cell) {
			return 'DNS';
		} else {
			console.log('cell', cell);
			return `${Number(cell).toFixed(decimalPlace)}`;
		}
	}

	const simpleStyle = {
		td: {
			'font-size': '0.8em',
			padding: '2px 2px'

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

	let currentViewMode = 'simple';
	let currentColumns = simpleColumns;
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
		columns: currentColumns,
		search: false
	};

	let drawerToggle = false;

	// selection variables
	let selectedClub = 'All';
	let selectedRegion = 'All';
	let selectedCompetition = 'All';
	let selectedLevel = 'All';
	let selectedDivision = 'All';

	let clubs = [
		'All',
		'ARGOS Gymnastics Club',
		'Affinity Gymnastics Academy',
		'Aspiring GymSports',
		'Aspiring Gymsports',
		'Balclutha Gymnastics Club',
		'Blenheim Gymnastics Club',
		'Capital Gymnastics',
		'Central Gymnastics',
		'College Street Gymnastics Club',
		'Counties Manukau Gymnastics',
		'Dunedin Gymnastics Academy',
		'Dynamic Gymnastic Sports',
		'Dynamic Gymnastics Sports',
		'Eastern Suburbs Gymnastics Club',
		'Fantastic Gymnastics',
		'Franklin Gymnastics',
		'Gisborne Gymnastics Club',
		'Gore Gymnastics Club',
		'Gymnastics Nelson',
		'Gymnastics Waitara',
		'Gymsport Manukau',
		'Hamilton City Gymnastics',
		'Harbour City Gymnastics',
		'Hastings Gymnastics Club',
		'Howick Gymnastics Club',
		'Huntly Gymnastics Club',
		'Hutt Valley Gymnastics',
		'ICE Gymsports North Canterbury',
		'Impact Gymsports Academy',
		'Invercargill Gymnastics Club',
		'Invert Sports Centre',
		'Kaitaia Gymnastics Club',
		'Kapiti Gymnastics',
		'Kerikeri Gymnastics Club',
		'Levin Gymnastics Club',
		'Manawatu Gymsports',
		'Mid Island Gym Sports',
		'Mt Tauhara Gymnastics Club',
		'North Harbour Gymnastics',
		'Olympia Gymnastics Sport',
		'Omni Gymnastics Centre',
		'Onslow Gymnastics Club',
		'Pathfinders Gymnastics Club',
		'Piako Gymnastics Club',
		'Queenstown Gymnastics Club',
		'Rimutaka Gymsports',
		'South Canterbury Gymsports',
		'St Bernadettes Gymnastics Club',
		'Te Awamutu',
		'Te Puke Gymsports',
		'Te Wero Gymnastics',
		'Timaru Gymnastics Club',
		'Tri Star Gymnastics',
		'Turn and Gymnastics Circle',
		'Twisters Tawa Gymnastics Club',
		'Waimate Gymnastics Club',
		'Waitakere Gymnastics Club',
		'West Melton Gymnastics Club',
		'Whanganui Boys & Girls Gym Club',
		'Whangarei Academy of Gymnastics'
	];

	let competitions = [
		'All',
		'Levin',
		'2022 Tri Star Elementary Championships',
		'2022 Te Wero Whakataetae',
		'South Island Gymnastics Championships 2022',
		'Rimutaka Junior Champs 2022',
		'Midlands Junior Artistic Competition 2022',
		'Kapiti Championships',
		'Hastings Gymnastics Junior Competition 2022',
		'Hamilton City Junior Artistic Competition 2022',
		'College Street Junior Competition 2022',
		'2022 New Zealand Gymnastics Championships - Artistic',
		'Canterbury Intermediate & Senior Championships 2022',
		'Auckland Manukau Champs',
		'2022 Central Champs',
		'Capital Juniors 2022',
		'Midlands Junior-Senior Artistic Championships 2022',
		'2022 Tri Star Championships and NZSS',
		'Southern Artistic Championships Competition',
		'WAGS Senior Club Competition ART (Qualifier)',
		'Manawatu Senior Opens',
		'Gymnastics Waitara - Senior Opens 2022',
		'HBPB Opens',
		'CSG Classic 2022',
		'Hamilton City Senior Artistic Competition 2022',
		'DGA Interclub Competition',
		'KB Memorial 2022',
		'MIGS Junior-Senior Artistic Competition 2022',
		'HBPB Juniors',
		'Affinity Gymnastics Academy Junior & Senior Challenge 2022',
		'Hutt Valley Competition 2022',
		'Wellington Champs 2022',
		'Manawatu Junior Opens',
		'Twisters Elementary 2022'
	];

	let levels = ['All', 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 'JI', 'SI'];

	function updateTableData() {
		let filteredData = dataset;

		if (selectedClub != 'All') {
			filteredData = filteredData.filter((row) => row.club === selectedClub);
		}

		if (selectedDivision != 'All') {
			filteredData = filteredData.filter((row) => row.division === selectedDivision);
		}

		if (selectedLevel != 'All') {
			filteredData = filteredData.filter((row) => row.level === selectedLevel);
		}

		if (selectedCompetition != 'All') {
			filteredData = filteredData.filter((row) => row.competition === selectedCompetition);
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

		let filteredData = dataset;

		if (selectedClub != 'All') {
			filteredData = filteredData.filter((row) => row.club === selectedClub);
		}

		if (selectedDivision != 'All') {
			filteredData = filteredData.filter((row) => row.division === selectedDivision);
		}

		if (selectedLevel != 'All') {
			filteredData = filteredData.filter((row) => row.level === selectedLevel);
		}

		if (selectedCompetition != 'All') {
			filteredData = filteredData.filter((row) => row.competition === selectedCompetition);
		}

		let tableKeys = Object.keys(filteredData[0]);

		csvGenerator(filteredData, tableKeys, tableHeader, filename);
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

<div class="container mx-auto">
	<div class="flex flex-row flex-wrap">
		<aside class="w-full sm:w-1/3 md:w-1/4">
			<div class="sticky top-0 w-full py-4 pr-2">
				<p class="text-xl font-bold">Womens Artistic Gymnastics</p>
				<ul class="menu overflow-y-auto bg-base-100 text-base-content">
					<!-- Sidebar content here -->
					<form>
						<!-- Results per page
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
						</div>-->
						<!-- View Mode 
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
						</div>-->

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
								name="level-select"
								class="select select-bordered w-full max-w-xs"
								bind:value={selectedLevel}
								on:change={updateTableData}
							>
								{#each levels as level}
									<option>{level}</option>
								{/each}
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
								<option>NONE</option>
							</select>
							<p>Competition</p>
							<select
								name=""
								id=""
								class="select select-bordered w-full max-w-xs"
								bind:value={selectedCompetition}
								on:change={updateTableData}
							>
								{#each competitions as comp}
									<option>{comp}</option>
								{/each}
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

						<button class="btn btn-secondary btn-block" on:click={downloadCSV}
							>Download CSV of current table</button
						>

						<!-- Buttons -->
						<div>
							<!-- Apply -->

							<!-- Download -->
						</div>
					</form>
				</ul>
			</div>
		</aside>
		<main role="main" class="w-full sm:w-2/3 md:w-3/4 pt-1 px-2">
			<Grid {...pkg} bind:instance={grid}/>
		</main>
	</div>
</div>
<footer class="mt-auto">...</footer>

<style global>
	@import 'https://cdn.jsdelivr.net/npm/gridjs/dist/theme/mermaid.min.css';
</style>
