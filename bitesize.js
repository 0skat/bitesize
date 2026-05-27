#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const axios = require('axios');
const chalk = require('chalk');
const { program } = require('commander');
const { convert } = require('html-to-text');

const DATA_FILE = path.join(__dirname, 'data.json');

function readData() {
    if (!fs.existsSync(DATA_FILE)) {
        return { topics: [], history: {} };
    }
    return JSON.parse(fs.readFileSync(DATA_FILE, 'utf8'));
}

function saveData(data) {
    fs.writeFileSync(DATA_FILE, JSON.stringify(data, null, 2));
}

async function fetchExternalContent(url) {
    try {
        const response = await axios.get(url, { 
            timeout: 5000,
            headers: { 'User-Agent': 'BiteSizeBot/1.0' }
        });
        const text = convert(response.data, {
            wordwrap: 130,
            selectors: [
                { selector: 'a', options: { ignoreHref: true } },
                { selector: 'img', format: 'skip' },
                { selector: 'nav', format: 'skip' },
                { selector: 'footer', format: 'skip' },
                { selector: 'script', format: 'skip' }
            ]
        });
        // Take the first 1500 chars as a "bite"
        return text.split('\n').filter(line => line.trim().length > 40).slice(0, 15).join('\n');
    } catch (e) {
        return null;
    }
}

program
    .version('1.1.0')
    .description('BiteSize - Your personal topic explorer');

program
    .command('follow <topic>')
    .description('Follow a new topic')
    .action((topic) => {
        const data = readData();
        if (!data.topics.includes(topic.toLowerCase())) {
            data.topics.push(topic.toLowerCase());
            saveData(data);
            console.log(chalk.green(`✔ Started following: ${chalk.bold(topic)}`));
        } else {
            console.log(chalk.yellow(`! You are already following ${topic}`));
        }
    });

program
    .command('list')
    .description('List all followed topics')
    .action(() => {
        const data = readData();
        if (data.topics.length === 0) {
            console.log(chalk.cyan('You are not following any topics yet. Use "follow <topic>" to start!'));
        } else {
            console.log(chalk.blue.bold('\nYour followed topics:'));
            data.topics.forEach(t => console.log(chalk.magenta(` • ${t}`)));
            console.log('');
        }
    });

program
    .command('fetch <topic>')
    .description('Fetch a new piece of info for a topic')
    .action(async (topic) => {
        const data = readData();
        const normalizedTopic = topic.toLowerCase();
        
        if (!data.topics.includes(normalizedTopic)) {
            console.log(chalk.red(`Error: You are not following "${topic}".`));
            process.exit(1);
        }

        console.log(chalk.gray(`\nSearching for insights on "${topic}"...`));

        try {
            // Search for more informative content specifically
            const searchQuery = `${topic} (tutorial OR tip OR news OR release OR "how to")`;
            const response = await axios.get(`https://www.reddit.com/r/all/search.json?q=${encodeURIComponent(searchQuery)}&sort=hot&limit=10`, {
                headers: { 'User-Agent': 'BiteSizeBot/1.0' }
            });

            const posts = response.data.data.children;
            const history = data.history[normalizedTopic] || [];

            // Find a post that is likely informative
            let selectedPost = null;
            for (const p of posts) {
                if (history.includes(p.data.id)) continue;
                
                // Filter out very short titles or obvious "help me" posts
                const title = p.data.title.toLowerCase();
                if (title.length < 20 || title.includes('help') || title.includes('error')) continue;
                
                selectedPost = p;
                break;
            }

            if (!selectedPost) {
                console.log(chalk.yellow(`No fresh, high-quality information found for "${topic}" right now.`));
                return;
            }

            // Mark as seen
            if (!data.history[normalizedTopic]) data.history[normalizedTopic] = [];
            data.history[normalizedTopic].push(selectedPost.data.id);
            saveData(data);

            let extractedInfo = selectedPost.data.selftext;
            let isExternal = false;

            // If it's a link and doesn't have much text, try fetching the external page
            if ((!extractedInfo || extractedInfo.length < 200) && selectedPost.data.url && !selectedPost.data.url.includes('reddit.com')) {
                const external = await fetchExternalContent(selectedPost.data.url);
                if (external) {
                    extractedInfo = external;
                    isExternal = true;
                }
            }

            // Build the output
            console.log(chalk.white.bgBlue.bold(` \n TOPIC: ${topic.toUpperCase()} `));
            console.log(chalk.bold.yellow(`\n${selectedPost.data.title}`));
            console.log(chalk.dim(`Source: r/${selectedPost.data.subreddit} • ${isExternal ? 'External Article' : 'Reddit Post'}\n`));
            
            if (extractedInfo) {
                console.log(chalk.white(extractedInfo.substring(0, 1000) + (extractedInfo.length > 1000 ? '...' : '')));
            } else {
                console.log(chalk.gray('(No additional text content available for this piece)'));
            }

            console.log('\n' + chalk.blue('---BITESIZE_RAW_DATA---'));
            console.log(JSON.stringify({
                topic: topic,
                title: selectedPost.data.title,
                content: extractedInfo || selectedPost.data.title,
                url: selectedPost.data.url
            }));
            console.log(chalk.blue('---END_RAW_DATA---\n'));

        } catch (error) {
            console.error(chalk.red('Failed to fetch info:'), error.message);
        }
    });

program.parse(process.argv);