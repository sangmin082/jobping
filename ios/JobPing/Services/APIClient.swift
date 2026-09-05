import Foundation

enum APIError: LocalizedError {
    case badURL
    case http(Int, String)
    case decoding(Error)
    case transport(Error)

    var errorDescription: String? {
        switch self {
        case .badURL: return "API 주소가 설정되지 않았습니다"
        case .http(let code, let msg): return "서버 오류 \(code): \(msg)"
        case .decoding: return "응답을 해석할 수 없습니다"
        case .transport(let e): return e.localizedDescription
        }
    }
}

/// 서버와의 유일한 통로. `API_BASE_URL` 은 Info.plist 로 들어오고, 빌드 시 xcconfig 가 채운다.
struct APIClient {
    let baseURL: URL
    private let session: URLSession

    init?(baseURLString: String? = Bundle.main.object(forInfoDictionaryKey: "APIBaseURL") as? String,
          session: URLSession = .shared) {
        guard let s = baseURLString, !s.isEmpty, let url = URL(string: s) else { return nil }
        self.baseURL = url
        self.session = session
    }

    func companies() async throws -> CompaniesResponse {
        try await get("v1/companies", query: [])
    }

    func jobs(companies: [String], since: String? = nil, limit: Int = 100) async throws -> JobsResponse {
        var q = [URLQueryItem(name: "companies", value: companies.joined(separator: ",")),
                 URLQueryItem(name: "limit", value: String(limit))]
        if let since { q.append(URLQueryItem(name: "since", value: since)) }
        return try await get("v1/jobs", query: q)
    }

    @discardableResult
    func register(_ device: DeviceRegistration) async throws -> DeviceResponse {
        var req = URLRequest(url: baseURL.appending(path: "v1/devices"))
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(device)
        return try await send(req)
    }

    private func get<T: Decodable>(_ path: String, query: [URLQueryItem]) async throws -> T {
        var comps = URLComponents(url: baseURL.appending(path: path), resolvingAgainstBaseURL: false)
        if !query.isEmpty { comps?.queryItems = query }
        guard let url = comps?.url else { throw APIError.badURL }
        return try await send(URLRequest(url: url))
    }

    private func send<T: Decodable>(_ request: URLRequest) async throws -> T {
        let (data, response): (Data, URLResponse)
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw APIError.transport(error)
        }
        let code = (response as? HTTPURLResponse)?.statusCode ?? 0
        guard (200..<300).contains(code) else {
            let msg = (try? JSONDecoder().decode([String: String].self, from: data))?["error"] ?? ""
            throw APIError.http(code, msg)
        }
        do {
            return try JSONDecoder().decode(T.self, from: data)
        } catch {
            throw APIError.decoding(error)
        }
    }
}
