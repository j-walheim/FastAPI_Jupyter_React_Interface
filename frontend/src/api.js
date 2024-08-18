export async function executeCode(code) {
  console.log('Sending code to server:', code);
  const response = await fetch('http://localhost:8000/execute', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ code }),
  });

  if (!response.ok) {
    throw new Error('Failed to execute code');
  }
  console.log('Code execution request successful');
}
