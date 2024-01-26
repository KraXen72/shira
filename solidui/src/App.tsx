import { createSignal } from 'solid-js';
import type { Component } from 'solid-js';

const wsurl = 'ws://localhost:8765/'
let ws: WebSocket;
ws_refresh()

const [wsState, set_wsState] = createSignal('closed')

function send() {
	console.log('attempting to send')
	ws.send('hello!!!')
}
function ws_refresh() {
	if (ws) ws.close()
	ws = new WebSocket(wsurl)
	ws.addEventListener("open", () => set_wsState('open')) 
	ws.addEventListener("close", () => set_wsState('closed'))
	ws.addEventListener("message", ({data}) => console.log(JSON.parse(data))) 
}

const App: Component = () => {
  return (
    <div>
      <h1>WEBUI</h1>
				<ul>
					<li>
						<button onClick={send}>Send message</button>
						<button onClick={ws_refresh}>Refresh connection</button>
					</li>
					<li>Open console to see messages from server</li>
					<li>Current state: {wsState()}</li>
				</ul>
    </div>
  );
};

export default App;
