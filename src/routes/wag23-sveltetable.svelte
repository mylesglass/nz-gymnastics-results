<script>
	import SvelteTable from "svelte-table";
	import dataset from '$lib/data/short-dataset.json';
	import ExpandedResults from "../components/expanded-results.svelte";

	// define column config
	const columns = [
		{
			key: "gnz",
			title: "GNZ #",
			value: v => v['gnz-id'],
			sortable: true
		},
		{
			key: "name",
			title: "Name",
			value: v => v['name'],
			sortable: true
		},
		{
			key: "club",
			title: "Club",
			value: v => v['club'],
			sortable: true,
			filterOptions: rows => {
				// use first letter of first_name to generate filter
				let clubs = {};
				rows.forEach(row => {
					let clubStr = row['club'];
					if (clubs[clubStr] === undefined)
					clubs[clubStr] = {
						name: clubStr,
						value: clubStr,
					};
				});
				// fix order
				clubs = Object.entries(clubs)
					.sort()
					.reduce((o, [k, v]) => ((o[k] = v), o), {});
				return Object.values(clubs);
			},
			filterValue: v => v['club']
		},
		{
			key: "level",
			title: "STEP",
			value: v => v['level'],
			sortable: true
		},
		{
			key: "division",
			title: "Division",
			value: v => v['division'],
			sortable: true
		},
		{
			key: "competition",
			title: "Competition",
			value: v => v['competition'].substring(0, 20),
			sortable: true
		},
		{
			key: "aa-score",
			title: "Total",
			value: v => formatCell(v['aa-score'], 3),
			sortable: true
		}
	];

	function formatCell(cell, decimalPlace) {
		if (isNaN(cell) || !cell) {
			return 'DNS';
		} else {
			return `${Number(cell).toFixed(decimalPlace)}`;
		}
	}

</script>

<SvelteTable 
	columns={columns} 
	rows={dataset} 
	showExpandIcon="{true}"
    expandSingle="{false}"
	rowKey="aa-score"
	classNameRow="border-b border-cyan-800"
	
>
	<ExpandedResults slot="expanded" let:row />
</SvelteTable>

<style>
	
</style>