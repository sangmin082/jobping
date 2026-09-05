import XCTest
@testable import JobPing

final class ModelTests: XCTestCase {
    func testDecodesJobsResponseFromServerShape() throws {
        let json = """
        {"jobs":[{"company":"sk_hynix","job_id":"abc","title":"DevOps Engineer","url":"https://x.com/1",
                  "first_seen_at":"2026-09-05T03:00:00+00:00","posted_at":null,"roles":["Infra"]}],
         "next_since":"2026-09-05T03:00:00+00:00"}
        """
        let resp = try JSONDecoder().decode(JobsResponse.self, from: Data(json.utf8))
        XCTAssertEqual(resp.jobs.count, 1)
        XCTAssertEqual(resp.jobs[0].id, "sk_hynix#abc")
        XCTAssertNotNil(resp.jobs[0].firstSeenDate)
        XCTAssertNil(resp.jobs[0].postedDate)
    }

    func testDecodesCompaniesWithFreeTier() throws {
        let json = """
        {"companies":[{"key":"sk_hynix","display_name":"SK하이닉스","source":"skcareers","group":"SK",
                       "last_success_at":null,"last_fetched":88}],
         "free_tier":{"max_keywords":1,"max_companies":3}}
        """
        let resp = try JSONDecoder().decode(CompaniesResponse.self, from: Data(json.utf8))
        XCTAssertEqual(resp.companies[0].displayName, "SK하이닉스")
        XCTAssertEqual(resp.freeTier.maxCompanies, 3)
    }

    func testISO8601AcceptsBothShapes() {
        XCTAssertNotNil(ISO8601.parse("2026-09-05T03:00:00+00:00"))
        XCTAssertNotNil(ISO8601.parse("2026-09-05T03:00:00.123Z"))
        XCTAssertNil(ISO8601.parse("곧"))
    }

    func testDeviceRegistrationUsesServerFieldNames() throws {
        let reg = DeviceRegistration(installId: "id", deviceToken: "ab", keywords: ["a"], companies: ["sk_hynix"],
                                     pushEnabled: true, appVersion: "0.1.0")
        let s = String(decoding: try JSONEncoder().encode(reg), as: UTF8.self)
        XCTAssertTrue(s.contains("\"install_id\""))
        XCTAssertTrue(s.contains("\"push_enabled\""))
    }
}
