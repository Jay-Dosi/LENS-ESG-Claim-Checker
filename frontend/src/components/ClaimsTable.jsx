export default function ClaimsTable({ claims, selectedClaim, onSelectClaim }) {
  const getClaimTypeColor = (type) => {
    const colors = {
      emissions_reduction: 'bg-green-600',
      net_zero_target: 'bg-blue-600',
      renewable_energy: 'bg-yellow-600',
      scope_1: 'bg-purple-600',
      scope_2: 'bg-purple-600',
      scope_3: 'bg-purple-600',
      energy_efficiency: 'bg-teal-600',
      carbon_offset: 'bg-orange-600',
    };
    return colors[type] || 'bg-gray-600';
  };

  const formatClaimType = (type) => {
    return type.split('_').map(word => 
      word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' ');
  };

  if (claims.length === 0) {
    return (
      <div className="bg-gray-700 rounded-lg p-8 text-center">
        <svg className="w-16 h-16 mx-auto text-gray-500 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <p className="text-gray-400">No claims extracted yet</p>
        <p className="text-sm text-gray-500 mt-2">Upload a sustainability report to begin</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {claims.map((claim) => (
        <div
          key={claim.claim_id}
          className={`bg-gray-700 hover:bg-gray-600 p-4 rounded-lg cursor-pointer transition border-2 ${
            selectedClaim?.claim_id === claim.claim_id ? 'border-blue-500' : 'border-transparent'
          }`}
          onClick={() => onSelectClaim(claim)}
        >
          <div className="flex items-start justify-between mb-2">
            <span className={`text-xs px-2 py-1 rounded ${getClaimTypeColor(claim.claim_type)} text-white font-semibold`}>
              {formatClaimType(claim.claim_type)}
            </span>
            <span className="text-xs bg-blue-600 px-2 py-1 rounded">
              {(claim.confidence * 100).toFixed(0)}% confidence
            </span>
          </div>

          <p className="text-sm text-gray-200 mb-2 line-clamp-2">
            {claim.claim_text}
          </p>

          <div className="flex items-center justify-between text-xs text-gray-400">
            <div className="flex items-center gap-4">
              <span>Page {claim.page_number}</span>
              {claim.value && (
                <span className="text-blue-400 font-semibold">
                  {claim.value}{claim.unit}
                </span>
              )}
              {claim.year && (
                <span>Year: {claim.year}</span>
              )}
            </div>
            <span className={`px-2 py-0.5 rounded text-xs ${
              claim.target_or_achieved === 'achieved' ? 'bg-green-900 text-green-300' :
              claim.target_or_achieved === 'target' ? 'bg-yellow-900 text-yellow-300' :
              'bg-gray-600 text-gray-300'
            }`}>
              {claim.target_or_achieved}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

// Made with Bob
