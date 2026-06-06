import { useState } from 'react'
import UploadModal from './components/UploadModal'
import ClaimsTable from './components/ClaimsTable'
import EvidencePanel from './components/EvidencePanel'
import { uploadDocument, extractClaims, verifyClaims, scoreClaims, getMapData } from './services/api'

function App() {
  const [showUploadModal, setShowUploadModal] = useState(false)
  const [documentId, setDocumentId] = useState(null)
  const [companyName, setCompanyName] = useState('')
  const [claims, setClaims] = useState([])
  const [selectedClaim, setSelectedClaim] = useState(null)
  const [evidence, setEvidence] = useState([])
  const [mapData, setMapData] = useState(null)
  const [riskScore, setRiskScore] = useState(null)
  const [loading, setLoading] = useState(false)
  const [loadingMessage, setLoadingMessage] = useState('')
  const [error, setError] = useState(null)

  const handleUpload = async (file, company, latitude = null, longitude = null, locationName = null) => {
    try {
      setLoading(true)
      setError(null)
      setCompanyName(company)
      
      // Stage 1: Upload
      setLoadingMessage('Uploading document...')
      const uploadResponse = await uploadDocument(file, company, latitude, longitude, locationName)
      setDocumentId(uploadResponse.document_id)
      console.log('Upload complete:', uploadResponse.document_id)
      
      // Stage 2 & 3: Extract claims
      setLoadingMessage('Extracting ESG claims with AI...')
      const claimsResponse = await extractClaims(uploadResponse.document_id)
      setClaims(claimsResponse.claims)
      console.log('Claims extracted:', claimsResponse.claims.length)
      
      // Stage 4 & 5: Verify claims
      setLoadingMessage('Verifying claims with satellite and news data...')
      const verifyResponse = await verifyClaims(uploadResponse.document_id)
      setEvidence(verifyResponse.evidence)
      if (verifyResponse.claims) {
        setClaims(verifyResponse.claims);
        // Also update selected claim if it was already selected
        setSelectedClaim(prev => {
          if (!prev) return prev;
          const updated = verifyResponse.claims.find(c => c.claim_id === prev.claim_id);
          return updated || prev;
        });
      }
      console.log('Evidence collected:', verifyResponse.evidence.length)
      
      // Fetch map data
      setLoadingMessage('Loading facility locations...')
      try {
        const mapResponse = await getMapData(uploadResponse.document_id)
        setMapData(mapResponse)
        console.log('✅ Map data loaded successfully:', {
          total_locations: mapResponse.total_locations,
          locations: mapResponse.locations,
          facilities: Object.keys(mapResponse.facilities || {}).length
        })
      } catch (mapError) {
        console.error('❌ Failed to load map data:', mapError)
        setMapData(null)
        // Continue without map data - not critical for the flow
      }
      
      // Stage 6 & 7: Score and explain
      setLoadingMessage('Calculating risk score and generating explanation...')
      const scoreResponse = await scoreClaims(uploadResponse.document_id)
      console.log('Score response:', scoreResponse)
      
      // Ensure we have the risk_score object
      if (scoreResponse && scoreResponse.risk_score) {
        setRiskScore(scoreResponse.risk_score)
        console.log('Risk score set:', scoreResponse.risk_score.truth_score)
      } else {
        console.error('Invalid score response:', scoreResponse)
        throw new Error('Invalid scoring response received')
      }
      
      // Clear loading state
      setLoading(false)
      setLoadingMessage('')
      console.log('Processing complete!')
      
      // Auto-select first claim
      if (claimsResponse.claims.length > 0) {
        setSelectedClaim(claimsResponse.claims[0])
      }
    } catch (err) {
      console.error('Error in handleUpload:', err)
      setError(err.message || 'An error occurred during processing')
      setLoading(false)
      setLoadingMessage('')
    } finally {
      // Ensure loading is always cleared
      setLoading(false)
      setLoadingMessage('')
    }
  }

  const getRiskScoreColor = (score) => {
    if (score > 60) return 'text-risk-low'
    if (score > 30) return 'text-risk-medium'
    return 'text-risk-high'
  }

  const getRiskBandColor = (band) => {
    if (band === 'Low Risk') return 'bg-risk-low'
    if (band === 'Medium Risk') return 'bg-risk-medium'
    return 'bg-risk-high'
  }

  return (
    <div className="h-screen flex flex-col bg-gray-900 text-white">
      {/* Top Bar */}
      <header className="bg-gray-800 border-b border-gray-700 p-4 shadow-lg">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <span className="text-blue-400">🔍</span>
              ESG Claim Verification Assistant
            </h1>
            <p className="text-sm text-gray-400">ESG Verification • Powered by AI & spaCy</p>
          </div>
          
          {riskScore && (
            <div className="flex items-center gap-6">
              <div className="text-right">
                <p className="text-sm text-gray-400">Verification Score</p>
                <p className={`text-4xl font-bold ${getRiskScoreColor(riskScore.truth_score)}`}>
                  {riskScore.truth_score}/100
                </p>
                <span className={`inline-block mt-1 px-3 py-1 rounded-full text-sm font-semibold ${getRiskBandColor(riskScore.risk_band)}`}>
                  {riskScore.risk_band}
                </span>
              </div>
              <div className="text-right text-sm text-gray-400">
                <p>Company: <span className="text-white font-semibold">{companyName}</span></p>
                <p>Claims: <span className="text-white font-semibold">{claims.length}</span></p>
                <p>Evidence: <span className="text-white font-semibold">{evidence.length}</span></p>
              </div>
            </div>
          )}
          
          <button
            onClick={() => setShowUploadModal(true)}
            className="bg-blue-600 hover:bg-blue-700 px-6 py-3 rounded-lg font-semibold transition shadow-lg flex items-center gap-2"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
            Upload Report
          </button>
        </div>
      </header>

      {/* Error Banner */}
      {error && (
        <div className="bg-red-900 border-b border-red-700 p-3 text-center">
          <p className="text-sm">⚠️ {error}</p>
          <button
            onClick={() => setError(null)}
            className="text-xs underline ml-2"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Main Content - Three Pane Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Pane - PDF Viewer Placeholder (Hidden when document is loaded) */}
        {!documentId && (
          <div className="w-1/3 border-r border-gray-700 bg-gray-800 p-4 overflow-auto">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              Document Viewer
            </h2>
            
            <div className="bg-gray-700 rounded-lg h-full flex flex-col items-center justify-center p-8">
              <svg className="w-20 h-20 text-gray-500 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
              </svg>
              <p className="text-gray-400 text-center">Upload a PDF to begin analysis</p>
              <button
                onClick={() => setShowUploadModal(true)}
                className="mt-4 text-blue-400 hover:text-blue-300 text-sm underline"
              >
                Click here to upload
              </button>
            </div>
          </div>
        )}

        {/* Center Pane - Claims Table */}
        <div className={`${documentId ? 'w-1/2' : 'w-1/3'} border-r border-gray-700 bg-gray-800 p-4 overflow-auto transition-all duration-300`}>
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
            Extracted Claims
            {claims.length > 0 && (
              <span className="ml-2 bg-blue-600 text-xs px-2 py-1 rounded-full">
                {claims.length}
              </span>
            )}
          </h2>
          
          <ClaimsTable
            claims={claims}
            selectedClaim={selectedClaim}
            onSelectClaim={setSelectedClaim}
          />
        </div>

        {/* Right Pane - Evidence & Explanation */}
        <div className={`${documentId ? 'w-1/2' : 'w-1/3'} bg-gray-800 p-4 overflow-auto transition-all duration-300`}>
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Evidence & Analysis
          </h2>
          
          <EvidencePanel
            claim={selectedClaim}
            evidence={evidence}
            mapData={mapData}
            riskScore={riskScore}
          />
        </div>
      </div>

      {/* Upload Modal */}
      <UploadModal
        isOpen={showUploadModal}
        onClose={() => setShowUploadModal(false)}
        onUpload={handleUpload}
      />

      {/* Loading Overlay */}
      {loading && (
        <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50">
          <div className="bg-gray-800 p-8 rounded-lg max-w-md w-full">
            <div className="flex flex-col items-center">
              <div className="animate-spin rounded-full h-16 w-16 border-b-4 border-blue-500 mb-4"></div>
              <p className="text-xl font-semibold mb-2">Processing...</p>
              <p className="text-sm text-gray-400 text-center">{loadingMessage}</p>
              <div className="mt-4 w-full bg-gray-700 rounded-full h-2">
                <div className="bg-blue-500 h-2 rounded-full animate-pulse" style={{ width: '60%' }}></div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default App

// Made with Bob
