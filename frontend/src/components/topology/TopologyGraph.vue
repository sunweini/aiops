<template>
  <div class="topology-graph" :style="{ height }" ref="containerRef"></div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import cytoscape from 'cytoscape'

const props = defineProps({
  nodes: {
    type: Array,
    default: () => []
  },
  edges: {
    type: Array,
    default: () => []
  },
  height: {
    type: String,
    default: '400px'
  },
  layout: {
    type: String,
    default: 'cose'
  }
})

const emit = defineEmits(['node-click'])

const containerRef = ref(null)
let cy = null
let pulseInterval = null

const updateGraph = (nodes, edges) => {
  if (!cy) return

  cy.elements().remove()

  const cyNodes = nodes.map(n => ({
    group: 'nodes',
    data: { id: n.id, label: n.label, status: n.status }
  }))

  const cyEdges = edges.map((e, i) => {
    const isFault =
      nodes.find(n => n.id === e.source)?.status === 'critical' ||
      nodes.find(n => n.id === e.target)?.status === 'critical' ||
      nodes.find(n => n.id === e.source)?.status === 'blast' ||
      nodes.find(n => n.id === e.target)?.status === 'blast'
    return {
      group: 'edges',
      data: { id: `e${i}`, source: e.source, target: e.target },
      classes: isFault ? 'fault' : ''
    }
  })

  cy.add([...cyNodes, ...cyEdges])
  cy.layout({ name: props.layout, animate: true }).run()
  startPulse()
}

const startPulse = () => {
  if (pulseInterval) clearInterval(pulseInterval)
  pulseInterval = setInterval(() => {
    cy.nodes('[status = "critical"]').forEach(node => {
      const bw = parseFloat(node.style('border-width')) || 3
      node.style('border-width', bw >= 6 ? 3 : 6)
    })
  }, 800)
}

onMounted(() => {
  cy = cytoscape({
    container: containerRef.value,
    style: [
      {
        selector: 'node',
        style: {
          'background-color': '#73BF69',
          width: 60,
          height: 60,
          label: 'data(label)',
          color: '#fff',
          'font-family': 'DM Sans, sans-serif',
          'font-size': '11px',
          'text-valign': 'center',
          'text-halign': 'center',
          'font-weight': 'bold'
        }
      },
      {
        selector: 'node[status = "critical"]',
        style: {
          'background-color': '#F2495C',
          'border-color': '#FF4D4D',
          'border-width': 3
        }
      },
      {
        selector: 'node[status = "blast"]',
        style: {
          'background-color': '#F2495C',
          'shadow-blur': 20,
          'shadow-color': 'rgba(242, 73, 92, 0.4)',
          'shadow-offset-x': 0,
          'shadow-offset-y': 0
        }
      },
      {
        selector: 'node[status = "warning"]',
        style: { 'background-color': '#FADE2A' }
      },
      {
        selector: 'node[status = "healthy"]',
        style: { 'background-color': '#73BF69' }
      },
      {
        selector: 'edge',
        style: {
          width: 2,
          'line-color': '#2c3235',
          'target-arrow-color': '#2c3235',
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier'
        }
      },
      {
        selector: 'edge.fault',
        style: {
          width: 3,
          'line-color': '#F2495C',
          'target-arrow-color': '#F2495C'
        }
      }
    ]
  })

  cy.on('tap', 'node', (evt) => {
    emit('node-click', evt.target.id())
  })

  updateGraph(props.nodes, props.edges)
})

watch(() => [props.nodes, props.edges], () => {
  updateGraph(props.nodes, props.edges)
}, { deep: true })

watch(() => props.layout, () => {
  if (cy) {
    cy.layout({ name: props.layout, animate: true }).run()
  }
})

onUnmounted(() => {
  if (pulseInterval) clearInterval(pulseInterval)
  if (cy) cy.destroy()
})
</script>

<style scoped>
.topology-graph {
  background: var(--bg-surface);
  border-radius: var(--radius-lg);
  width: 100%;
}
</style>
