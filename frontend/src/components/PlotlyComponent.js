import React from 'react';
import Plot from 'react-plotly.js';

const PlotlyComponent = ({ data }) => {
  try {
    const plotData = JSON.parse(data);
    return <Plot data={plotData.data} layout={plotData.layout} />;
  } catch (error) {
    console.error('Error parsing Plotly data:', error);
    return <div>Error rendering plot</div>;
  }
};

export default PlotlyComponent;