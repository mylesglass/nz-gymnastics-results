# nz-gymnastics-results

A web app for viewing artistic gymnastics results from local New Zealand Competitions, powered by [`create-svelte`](https://github.com/sveltejs/kit/tree/master/packages/create-svelte).

## Under the hood
- [SvelteKit](https://kit.svelte.dev/)
- [Tailwind CSS](https://tailwindcss.com/docs/guides/sveltekit)
- [daisyUI](https://daisyui.com)
- [gridjs-svelte](https://github.com/iamyuu/gridjs-svelte)

## Data Sources

Easily the trickiest bit of this project, getting the data into a consistent format. All gymnastics results are publically available via the [Gymnastics NZ Event Calendar](https://www.gymnasticsnz.com/events-calendar-results/), but often in .pdf or .xlsx. Originally I tried to create a scraper to pull data from the .pdfs, but this turned to custard when the format of ScoreHolders exported .pdf changed and broke my scraper. 

In the constant search of trying to do as little work as possible, I found that you could pull the json blob right from ScoreHolders webapp. Now we're cooking with fire. 

All parsers are included in the `utils` folder, and work on Python 3.10.5. These are rough. I'm sorry to anyone that tries to use them. I hadn't done mush python work prior, so my structure is probably not ideal, and it just kept growing in length as more use cases appeared. 

For this project, all results are served on application load from a json file. This will likely be altered to a database when I begin to include 2023 results into the system.

## Building

To create a production version of the app:

```bash
npm run build
```

You can preview the production build with `npm run preview`.

> To deploy your app, you may need to install an [adapter](https://kit.svelte.dev/docs/adapters) for your target environment.