import React from 'react';
import Plot from 'react-plotly.js';

const PlotlyComponent = ({ plotData }) => {
  if (!plotData) return null;
  
  const parsedData = JSON.parse(plotData);
  
  return (
    <Plot
      data={parsedData.data}
      layout={parsedData.layout}
      config={parsedData.config}
      style={{ width: '100%', height: '100%' }}
    />
  );
};

export default PlotlyComponent;
