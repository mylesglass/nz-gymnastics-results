<div>
	<Grid data={dataset} {columns} {pagination} {sort} {style} {search} />
</div>

<script>
	import Grid from 'gridjs-svelte';

    export let dataset = [
        {
            "gnz-id": "no data"
        }
    ]
    export let perPage = 10;

	const style = {
		td: {
			'font-size': '0.8em'
		}
	};

    const search = {
        enabled: true
    };

	const pagination = {
		enabled: true,
		limit: perPage
	};

	const sort = {
		enable: true
	};

	const columns = [
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
</script>

<style global>
	@import 'https://cdn.jsdelivr.net/npm/gridjs/dist/theme/mermaid.min.css';
</style>
