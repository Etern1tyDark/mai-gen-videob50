require('global-agent/bootstrap')

global.GLOBAL_AGENT.HTTP_PROXY = 'http://127.0.0.1:7890'

const { generate } = require('youtube-po-token-generator')

generate().then(
    (result) => console.log(JSON.stringify(result)),
    (error) => console.error(JSON.stringify({ error: error.message }))
)